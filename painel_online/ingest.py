"""Gravar ofertas recebidas: valida, decide novo/atualização, grava oferta e preço."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from .db import agora_iso, transacao
from .schemas import OfertaIn
from .upsert import chave_da_oferta, decidir

MAX_DETALHES = 50  # quantas ofertas ignoradas listamos na resposta


def _iso_utc(dt: datetime) -> str:
    # Sem fuso informado, assumimos UTC (o painel local vai mandar com fuso na Etapa 4).
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _resumir(erro: ValidationError) -> str:
    partes = []
    for e in erro.errors()[:3]:
        campo = ".".join(str(x) for x in e["loc"]) or "oferta"
        partes.append(f"{campo}: {e['msg']}")
    return "; ".join(partes)


def ingerir(con: sqlite3.Connection, usuario_id: int, itens: list[Any]) -> dict:
    """Grava um lote de ofertas em uma transação só (tudo ou nada).

    Devolve quantas foram criadas, atualizadas e ignoradas. Ignoradas são as que
    não passaram na validação ou cujo produto foi descartado no painel.
    """
    criadas = atualizadas = 0
    ignoradas: list[dict] = []
    agora = agora_iso()

    with transacao(con):
        # Carregado DENTRO da transação: ninguém grava no meio e cria duplicado.
        existentes = {(r["loja"], r["id_produto"]): r["id"] for r in con.execute("SELECT id, loja, id_produto FROM ofertas")}
        descartados = {
            (r["loja"], r["id_produto"])
            for r in con.execute("SELECT o.loja, o.id_produto FROM descartados d JOIN ofertas o ON o.id = d.oferta_id")
        }
        for i, bruto in enumerate(itens):
            try:
                oferta = OfertaIn.model_validate(bruto)
            except ValidationError as e:
                ignoradas.append({"indice": i, "motivo": _resumir(e)})
                continue

            chave = chave_da_oferta(oferta)
            if chave in descartados:
                ignoradas.append({"indice": i, "motivo": "produto descartado no painel"})
                continue

            coletado = _iso_utc(oferta.coletado_em) if oferta.coletado_em else agora
            campos = {
                "url": oferta.url,
                "titulo": oferta.titulo,
                "preco": oferta.preco,
                "preco_original": oferta.preco_original,
                "desconto": oferta.desconto,
                "parcelamento": oferta.parcelamento,
                "imagem": oferta.imagem,
                "categoria": oferta.categoria,
                "deal_score": oferta.deal_score,
                "deal_confianca": oferta.deal_confianca,
                "deal_motivos": json.dumps(oferta.deal_motivos, ensure_ascii=False),
                "deal_flags": json.dumps(oferta.deal_flags, ensure_ascii=False),
                "coletado_em": coletado,
                "atualizado_em": agora,
                "enviado_por": usuario_id,
            }

            if decidir(oferta, existentes.keys()) == "novo":
                colunas = ["loja", "id_produto", "criado_em", *campos]
                valores = [chave[0], chave[1], agora, *campos.values()]
                cur = con.execute(
                    f"INSERT INTO ofertas ({', '.join(colunas)}) VALUES ({', '.join('?' * len(colunas))})", valores
                )
                oferta_id = cur.lastrowid
                existentes[chave] = oferta_id
                criadas += 1
            else:
                oferta_id = existentes[chave]
                # imagem e categoria: se o envio novo não trouxe, mantém a que já existia
                sets = ", ".join(
                    f"{c} = COALESCE(?, {c})" if c in ("imagem", "categoria") else f"{c} = ?" for c in campos
                )
                con.execute(f"UPDATE ofertas SET {sets} WHERE id = ?", [*campos.values(), oferta_id])
                atualizadas += 1

            # Todo envio vira uma linha de histórico de preço.
            con.execute(
                "INSERT INTO precos (oferta_id, preco, coletado_em, enviado_por) VALUES (?, ?, ?, ?)",
                (oferta_id, oferta.preco, coletado, usuario_id),
            )

    return {
        "criadas": criadas,
        "atualizadas": atualizadas,
        "ignoradas": len(ignoradas),
        "detalhes_ignoradas": ignoradas[:MAX_DETALHES],
    }
