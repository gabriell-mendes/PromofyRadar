"""Etapa 5: o que dá para provar sem o VPS: backup, saúde, requisitos enxutos e arquivos de deploy."""

import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from painel_online import backup
from painel_online.ingest import ingerir

RAIZ = Path(__file__).resolve().parent.parent
OFERTA = {"loja": "mercadolivre", "url": "https://www.mercadolivre.com.br/x/p/MLB25171538", "titulo": "Produto", "preco": 10.0}


@pytest.fixture
def banco(painel):
    painel.admin("ana")
    ingerir(painel.con, painel.ids["ana"], [OFERTA])
    return painel


def contar(db: Path, tabela: str) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    finally:
        con.close()


# ---------- saúde ----------
def test_saude_responde_sem_login(painel):
    r = painel.cliente().get("/api/saude")
    assert r.status_code == 200 and r.json() == {"ok": True}


# ---------- backup ----------
def test_backup_copia_o_banco_com_os_dados(banco, tmp_path):
    db = tmp_path / "painel.db"
    destino = backup.fazer_backup(db, tmp_path / "bk")
    assert destino.parent == tmp_path / "bk" and destino.name.startswith("painel-") and destino.suffix == ".db"
    assert contar(destino, "ofertas") == 1 and contar(destino, "usuarios") == 1 and contar(destino, "precos") == 1
    assert not list((tmp_path / "bk").glob("*.parcial"))


def test_backup_pega_o_que_ainda_esta_no_wal(banco, tmp_path):
    # Dado gravado e ainda não "fechado" no arquivo principal (modo WAL): copiar o .db na mão perderia isso.
    ingerir(banco.con, banco.ids["ana"], [{**OFERTA, "url": "https://x.com/p/MLB99999999", "titulo": "Outro"}])
    assert (tmp_path / "painel.db-wal").exists()
    destino = backup.fazer_backup(tmp_path / "painel.db", tmp_path / "bk")
    assert contar(destino, "ofertas") == 2


def test_backup_padrao_fica_ao_lado_do_banco(banco, tmp_path):
    destino = backup.fazer_backup(tmp_path / "painel.db")
    assert destino.parent == tmp_path / "backups"


def test_rotacao_guarda_so_os_mais_recentes(banco, tmp_path):
    db, pasta = tmp_path / "painel.db", tmp_path / "bk"
    base = datetime(2026, 10, 1, 3, 15)
    for i in range(5):
        backup.fazer_backup(db, pasta, manter=3, agora=base + timedelta(days=i))
    nomes = sorted(p.name for p in pasta.glob("painel-*.db"))
    assert nomes == ["painel-2026-10-03-031500.db", "painel-2026-10-04-031500.db", "painel-2026-10-05-031500.db"]


@pytest.mark.skipif(sys.platform == "win32", reason="permissões de arquivo são do Linux")
def test_backup_nao_e_legivel_por_qualquer_um(banco, tmp_path):
    destino = backup.fazer_backup(tmp_path / "painel.db", tmp_path / "bk")
    assert destino.stat().st_mode & 0o777 == 0o640  # dono lê e grava, grupo só lê, outros nada


def test_backup_de_banco_inexistente_ou_corrompido_falha_sem_lixo(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup.fazer_backup(tmp_path / "nao-existe.db", tmp_path / "bk")
    ruim = tmp_path / "ruim.db"
    ruim.write_bytes(b"isto nao e um banco sqlite" * 100)
    with pytest.raises(sqlite3.DatabaseError):
        backup.fazer_backup(ruim, tmp_path / "bk")
    assert not list((tmp_path / "bk").glob("*"))


def test_cli_do_backup(banco, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PAINEL_DB", str(tmp_path / "painel.db"))
    assert backup.main(["x", "--pasta", str(tmp_path / "bk"), "--manter", "2"]) == 0
    assert "backup ok" in capsys.readouterr().out
    monkeypatch.setenv("PAINEL_DB", str(tmp_path / "nao-existe.db"))
    assert backup.main(["x", "--pasta", str(tmp_path / "bk")]) == 1
    assert "BACKUP FALHOU" in capsys.readouterr().err


# ---------- o VPS não roda scraper ----------
def test_painel_online_nao_depende_de_scraper():
    proibidos = re.compile(r"^\s*(import|from)\s+(playwright|requests|bs4|techdrop_server|scraper\w*)\b", re.M)
    for arquivo in (RAIZ / "painel_online").glob("*.py"):
        assert not proibidos.search(arquivo.read_text(encoding="utf-8")), arquivo.name
    reqs = (RAIZ / "requirements-painel.txt").read_text(encoding="utf-8").lower()
    pacotes = {re.split(r"[=<>\[ ]", l.strip())[0] for l in reqs.splitlines() if l.strip() and not l.startswith("#")}
    assert pacotes == {"fastapi", "uvicorn", "bcrypt"}


# ---------- arquivos de deploy coerentes entre si ----------
def ler(nome: str) -> str:
    return (RAIZ / "deploy" / nome).read_text(encoding="utf-8")


def test_servico_escuta_so_em_localhost_e_o_caddy_aponta_para_a_mesma_porta():
    exec_start = re.search(r"^ExecStart=(.+)$", ler("painel.service"), re.M).group(1)
    assert "painel_online.app:app" in exec_start and "--host 127.0.0.1" in exec_start
    assert "0.0.0.0" not in exec_start
    porta = re.search(r"--port (\d+)", exec_start).group(1)
    assert f"reverse_proxy 127.0.0.1:{porta}" in ler("Caddyfile")


def test_servico_e_cron_usam_o_mesmo_banco_e_caminhos():
    banco_servico = re.search(r"^Environment=PAINEL_DB=(.+)$", ler("painel.service"), re.M).group(1)
    banco_cron = re.search(r"^PAINEL_DB=(.+)$", ler("painel.cron"), re.M).group(1)
    assert banco_servico == banco_cron == "/var/lib/painel/painel.db"
    assert "-m painel_online.backup" in ler("painel.cron")
    assert "User=painel" in ler("painel.service") and "NoNewPrivileges=true" in ler("painel.service")


def test_caddy_limita_o_corpo_igual_ao_painel():
    from painel_online import app as app_mod

    assert "max_size 1MB" in ler("Caddyfile") and app_mod.MAX_BYTES == 1_000_000


def test_arquivos_de_deploy_sem_segredo_e_script_com_erro_fatal():
    tudo = "".join(ler(n) for n in ("painel.service", "Caddyfile", "painel.cron", "atualizar.sh"))
    assert not re.search(r"td_[A-Za-z0-9_-]{20,}", tudo)
    assert "set -euo pipefail" in ler("atualizar.sh")
