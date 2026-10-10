"""Backup do banco do painel online.

    venv/bin/python -m painel_online.backup [--manter N] [--pasta CAMINHO]

Usa a API de backup do próprio SQLite: gera uma cópia consistente mesmo com o painel
no ar e gravando (copiar o arquivo .db na mão pode pegar um estado pela metade, por
causa do modo WAL). A cópia é conferida (`integrity_check`) antes de valer, e os
backups mais antigos além de N são apagados.

Padrão: pasta `backups/` ao lado do banco (PAINEL_DB), 14 cópias. Essa pasta está no
mesmo disco do servidor: copie também para fora dele (ver docs/deploy-vps.md).
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from .db import caminho_db

PADRAO_MANTER = 14


def fazer_backup(db_path: str | Path, pasta: str | Path | None = None, manter: int = PADRAO_MANTER,
                 agora: datetime | None = None) -> Path:
    """Cria `painel-AAAA-MM-DD-HHMMSS.db` na pasta e devolve o caminho. Levanta RuntimeError
    se a cópia não passar na conferência (nesse caso nada é guardado)."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Banco não encontrado: {db_path}")
    pasta = Path(pasta) if pasta else db_path.parent / "backups"
    pasta.mkdir(parents=True, exist_ok=True)

    nome = f"painel-{(agora or datetime.now()):%Y-%m-%d-%H%M%S}.db"
    final = pasta / nome
    temporario = pasta / (nome + ".parcial")  # só vira backup de verdade depois de conferido

    origem = sqlite3.connect(db_path)
    copia = sqlite3.connect(temporario)
    try:
        origem.backup(copia)
        resultado = copia.execute("PRAGMA integrity_check").fetchone()[0]
    except BaseException:
        copia.close()
        origem.close()
        temporario.unlink(missing_ok=True)  # não deixa meia cópia pela pasta
        raise
    copia.close()
    origem.close()
    if resultado != "ok":
        temporario.unlink(missing_ok=True)
        raise RuntimeError(f"A cópia falhou na conferência: {resultado}")

    try:
        # O banco tem hashes de senha e tokens: só o dono e o grupo (o admin que copia o backup) leem.
        os.chmod(temporario, 0o640)
    except OSError:
        pass  # Windows
    temporario.replace(final)

    for velho in sorted(pasta.glob("painel-*.db"))[:-manter] if manter > 0 else []:
        velho.unlink()
    return final


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Backup do banco do painel online")
    ap.add_argument("--manter", type=int, default=PADRAO_MANTER, help="quantos backups guardar (padrão 14)")
    ap.add_argument("--pasta", help="pasta de destino (padrão: backups/ ao lado do banco)")
    args = ap.parse_args(argv[1:])
    try:
        destino = fazer_backup(caminho_db(), args.pasta, args.manter)
    except (OSError, RuntimeError, sqlite3.Error) as e:
        print(f"BACKUP FALHOU: {e}", file=sys.stderr)
        return 1
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} backup ok: {destino} ({destino.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
