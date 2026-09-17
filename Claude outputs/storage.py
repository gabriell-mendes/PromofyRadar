"""Persistência simples das ofertas (SQLite).

Primeiro passo real de "armazenamento" do roadmap (ver docs/roadmap.md).
De propósito, NÃO é PostgreSQL: SQLite é um arquivo só, sem servidor pra
configurar, e resolve exatamente o que falta hoje — lembrar entre uma
busca e outra quais ofertas você já viu e o que já foi enviado pro grupo.
Trocar por Postgres mais tarde, se algum dia fizer sentido (mais de um
processo escrevendo ao mesmo tempo, por exemplo), não deveria exigir
mudar a assinatura das funções deste arquivo — só a implementação por
dentro delas.

Isso NÃO é ainda "histórico de preços" (série temporal por produto,
registrado como item separado em docs/roadmap.md): aqui cada oferta tem
UMA linha, que é atualizada (preço, score) toda vez que ela reaparece
numa busca nova. Preço de ontem não fica guardado. Série temporal de
verdade é um passo futuro, deliberadamente não implementado agora.

Chave de identidade de uma oferta: (source, source_id) — os mesmos campos
que já identificam um Product de forma única dentro de uma fonte (ver
app/models.py). Duas buscas diferentes que trazem o mesmo produto
atualizam a MESMA linha, não criam duplicata.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from .models import Product

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ofertas.db"

STATUS_PENDENTE = "pendente"
STATUS_ENVIADA = "enviada"
STATUS_VALIDOS = (STATUS_PENDENTE, STATUS_ENVIADA)


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def _conexao() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    try:
        yield conexao
        conexao.commit()
    finally:
        conexao.close()


def inicializar_banco() -> None:
    """Cria a tabela se não existir. Chamado uma vez, na subida do app
    (ver app/main.py) — seguro de chamar de novo (CREATE TABLE IF NOT
    EXISTS), então não precisa de migração separada nesse estágio.
    """
    with _conexao() as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS ofertas (
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                price TEXT NOT NULL,
                original_price TEXT,
                url TEXT NOT NULL,
                store TEXT NOT NULL,
                score INTEGER NOT NULL,
                reason TEXT NOT NULL,
                desconto_percentual REAL,
                status TEXT NOT NULL DEFAULT 'pendente',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                sent_at TEXT,
                PRIMARY KEY (source, source_id)
            )
            """
        )


def salvar_oferta(
    produto: Product, score: int, reason: str, desconto_percentual: float | None
) -> None:
    """Insere a oferta se for nova, ou atualiza preço/score/data se ela já
    existir (mesma source + source_id) — sem mexer no status nem no
    sent_at, que só mudam por ação explícita (ver marcar_status).
    """
    agora = _timestamp()
    with _conexao() as conexao:
        conexao.execute(
            """
            INSERT INTO ofertas (
                source, source_id, title, price, original_price, url, store,
                score, reason, desconto_percentual, status,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source, source_id) DO UPDATE SET
                title = excluded.title,
                price = excluded.price,
                original_price = excluded.original_price,
                url = excluded.url,
                store = excluded.store,
                score = excluded.score,
                reason = excluded.reason,
                desconto_percentual = excluded.desconto_percentual,
                last_seen_at = excluded.last_seen_at
            """,
            (
                produto.source,
                produto.source_id,
                produto.title,
                str(produto.price),
                str(produto.original_price) if produto.original_price is not None else None,
                produto.url,
                produto.store,
                score,
                reason,
                desconto_percentual,
                STATUS_PENDENTE,
                agora,
                agora,
            ),
        )


def marcar_status(source: str, source_id: str, status: str) -> bool:
    """Muda o status de uma oferta já salva. Devolve False se a oferta não
    existir (ex: link velho, ou banco limpo) — quem chama decide o que
    fazer, não é levantado como erro porque não é uma falha do sistema.
    """
    if status not in STATUS_VALIDOS:
        raise ValueError(f"status inválido: {status!r}. Válidos: {STATUS_VALIDOS}")

    sent_at = _timestamp() if status == STATUS_ENVIADA else None
    with _conexao() as conexao:
        cursor = conexao.execute(
            "UPDATE ofertas SET status = ?, sent_at = ? WHERE source = ? AND source_id = ?",
            (status, sent_at, source, source_id),
        )
        return cursor.rowcount > 0


def _linha_para_dict(linha: sqlite3.Row) -> dict:
    return {
        "source": linha["source"],
        "source_id": linha["source_id"],
        "title": linha["title"],
        "price": Decimal(linha["price"]),
        "original_price": Decimal(linha["original_price"]) if linha["original_price"] else None,
        "url": linha["url"],
        "store": linha["store"],
        "score": linha["score"],
        "reason": linha["reason"],
        "desconto_percentual": linha["desconto_percentual"],
        "status": linha["status"],
        "first_seen_at": linha["first_seen_at"],
        "last_seen_at": linha["last_seen_at"],
        "sent_at": linha["sent_at"],
    }


def listar_ofertas(status: str | None = None, limit: int = 200) -> list[dict]:
    """Lista ofertas salvas, mais recentes primeiro (por last_seen_at)."""
    with _conexao() as conexao:
        if status is not None:
            linhas = conexao.execute(
                "SELECT * FROM ofertas WHERE status = ? ORDER BY last_seen_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            linhas = conexao.execute(
                "SELECT * FROM ofertas ORDER BY last_seen_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_linha_para_dict(linha) for linha in linhas]


def obter_status(source: str, source_id: str) -> str | None:
    """Status atual de uma oferta específica, ou None se ela nunca foi
    salva (ex: chegou de uma busca mas ainda não passou por
    salvar_oferta — não deveria acontecer no fluxo normal, mas não é
    motivo pra derrubar a página se acontecer).
    """
    with _conexao() as conexao:
        linha = conexao.execute(
            "SELECT status FROM ofertas WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
    return linha["status"] if linha else None


def contar_por_status() -> dict[str, int]:
    """Ex: {"pendente": 12, "enviada": 3}. Fontes sem nenhuma linha não
    aparecem no dict (em vez de aparecer com 0) — mais simples de
    templates/historico.html iterar sem checar chave ausente.
    """
    with _conexao() as conexao:
        linhas = conexao.execute(
            "SELECT status, COUNT(*) as total FROM ofertas GROUP BY status"
        ).fetchall()
    return {linha["status"]: linha["total"] for linha in linhas}
