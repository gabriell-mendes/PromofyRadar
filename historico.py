"""Historico de precos (SQLite), um registro por produto por dia.

Por que um por dia: rodar o scraper 5 vezes num dia nao pode dar 5x mais
peso para aquele dia na mediana. Se o mesmo produto aparece de novo no mesmo
dia, o registro do dia e atualizado com o preco mais recente.

Arquivo: data/historico_precos.db, ou o caminho em TECHDROP_HISTORICO_DB
(os scrapers de teste usam outro arquivo para nao sujar o historico real).
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Iterator

DB_PADRAO = Path(__file__).resolve().parent / "data" / "historico_precos.db"
JANELA_DIAS = 30


def caminho_db(db: str | Path | None = None) -> Path:
    if db:
        return Path(db)
    return Path(os.environ.get("TECHDROP_HISTORICO_DB") or DB_PADRAO)


@contextmanager
def _conexao(db: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    caminho = caminho_db(db)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS precos (
            chave TEXT NOT NULL,
            dia TEXT NOT NULL,
            preco REAL NOT NULL,
            PRIMARY KEY (chave, dia)
        )
        """
    )
    try:
        yield con
        con.commit()
    finally:
        con.close()


def chave_produto(link: str) -> str:
    """Identidade estavel do produto entre coletas.

    O link do ML muda de parametros a cada busca (pdp_filters, searchVariation,
    tracking). Usamos o codigo MLB quando existe; senao o link sem query string.
    O codigo e procurado so no caminho: na query, `pdp_filters=deal:MLB779362-1` e o
    id da promocao e fazia produtos diferentes cairem na mesma chave. Links `/up/`
    usam MLBU (MLBU3367167774), que tambem e aceito.
    """
    caminho = (link or "").split("#")[0].split("?")[0]
    m = re.search(r"MLB(U?)-?(\d{6,})", caminho)
    if m:
        return f"MLB{m.group(1)}{m.group(2)}"
    return caminho


def registrar(observacoes: Iterable[tuple[str, float]], quando: date | None = None,
              db: str | Path | None = None) -> int:
    """Grava (chave, preco) no dia `quando` (hoje por padrao). Devolve quantos gravou."""
    dia = (quando or date.today()).isoformat()
    linhas = [(c, dia, float(p)) for c, p in observacoes if c and p and p > 0]
    if not linhas:
        return 0
    with _conexao(db) as con:
        con.executemany(
            "INSERT INTO precos (chave, dia, preco) VALUES (?, ?, ?) "
            "ON CONFLICT (chave, dia) DO UPDATE SET preco = excluded.preco",
            linhas,
        )
    return len(linhas)


def obter(chaves: Iterable[str], antes_de: date | None = None, dias: int = JANELA_DIAS,
          db: str | Path | None = None) -> dict[str, list[float]]:
    """Precos dos `dias` dias ANTERIORES a `antes_de` (hoje nao entra), por chave."""
    fim = antes_de or date.today()
    inicio = fim - timedelta(days=dias)
    chaves = list(set(chaves))
    saida: dict[str, list[float]] = {c: [] for c in chaves}
    if not chaves:
        return saida
    with _conexao(db) as con:
        # em lotes, para nao estourar o limite de parametros do SQLite
        for i in range(0, len(chaves), 500):
            lote = chaves[i:i + 500]
            marcas = ",".join("?" * len(lote))
            cur = con.execute(
                f"SELECT chave, preco FROM precos WHERE chave IN ({marcas}) "
                "AND dia >= ? AND dia < ? ORDER BY dia",
                [*lote, inicio.isoformat(), fim.isoformat()],
            )
            for chave, preco in cur:
                saida[chave].append(preco)
    return saida
