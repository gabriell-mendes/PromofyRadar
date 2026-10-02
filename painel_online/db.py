"""Banco SQLite do painel online: conexão, tabelas e o token de API.

Sem ORM: SQL direto com sqlite3 da biblioteca padrão. O banco é um arquivo só,
suficiente para poucos administradores enviando de vez em quando.
"""

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request

from .credenciais import hash_senha, validar_senha

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PADRAO = BASE_DIR / "data" / "painel_online.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY,
    nome        TEXT NOT NULL UNIQUE,
    senha_hash  TEXT,                       -- preenchida na Etapa 3 (login web)
    criado_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tokens_api (
    id          INTEGER PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    token_hash  TEXT NOT NULL UNIQUE,       -- sha256 do token; o token em si nunca fica aqui
    rotulo      TEXT,
    criado_em   TEXT NOT NULL,
    revogado_em TEXT                        -- preenchido = token não vale mais
);

CREATE TABLE IF NOT EXISTS sessoes (
    id_hash     TEXT PRIMARY KEY,           -- sha256 do valor do cookie; o cookie em si nunca fica aqui
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    criado_em   TEXT NOT NULL,
    expira_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ofertas (
    id              INTEGER PRIMARY KEY,
    loja            TEXT NOT NULL,
    id_produto      TEXT NOT NULL,
    url             TEXT NOT NULL,
    titulo          TEXT NOT NULL,
    preco           REAL NOT NULL,
    preco_original  REAL,
    desconto        REAL,
    parcelamento    TEXT,
    imagem          TEXT,
    categoria       TEXT,
    deal_score      INTEGER,
    deal_confianca  TEXT,
    deal_motivos    TEXT NOT NULL DEFAULT '[]',   -- lista em JSON
    deal_flags      TEXT NOT NULL DEFAULT '[]',   -- lista em JSON
    coletado_em     TEXT NOT NULL,
    criado_em       TEXT NOT NULL,
    atualizado_em   TEXT NOT NULL,
    enviado_por     INTEGER NOT NULL REFERENCES usuarios(id),  -- quem enviou por último
    UNIQUE (loja, id_produto)
);

CREATE TABLE IF NOT EXISTS precos (
    id           INTEGER PRIMARY KEY,
    oferta_id    INTEGER NOT NULL REFERENCES ofertas(id),
    preco        REAL NOT NULL,
    coletado_em  TEXT NOT NULL,
    enviado_por  INTEGER NOT NULL REFERENCES usuarios(id)
);
CREATE INDEX IF NOT EXISTS idx_precos_oferta ON precos (oferta_id);

CREATE TABLE IF NOT EXISTS descartados (
    oferta_id       INTEGER PRIMARY KEY REFERENCES ofertas(id),
    descartado_em   TEXT NOT NULL,
    descartado_por  INTEGER NOT NULL REFERENCES usuarios(id)
);
"""


def caminho_db() -> Path:
    return Path(os.environ.get("PAINEL_DB") or DB_PADRAO)


def conectar(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: nós mesmos abrimos e fechamos as transações (ver `transacao`).
    # check_same_thread=False: o FastAPI pode usar a conexão em outra thread da mesma requisição.
    con = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")  # leitores não travam o gravador
    return con


def criar_tabelas(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


@contextmanager
def transacao(con: sqlite3.Connection):
    """Tudo ou nada. BEGIN IMMEDIATE trava a escrita desde o início, então dois PCs
    enviando o mesmo produto ao mesmo tempo não conseguem criar duplicado."""
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")


def get_con(request: Request):
    """Dependência do FastAPI: uma conexão por requisição, fechada no fim."""
    con = conectar(request.app.state.db_path)
    try:
        yield con
    finally:
        con.close()


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_token(token: str) -> str:
    # sha256 basta aqui: o token tem 256 bits aleatórios, não dá para adivinhar nem
    # fazer força bruta. Hash lento (bcrypt) é para senhas humanas, que são fracas.
    return hashlib.sha256(token.encode()).hexdigest()


def criar_usuario(con: sqlite3.Connection, nome: str, senha: str) -> int:
    """Cria o administrador com a senha em hash. Levanta ValueError se a senha for fraca
    e sqlite3.IntegrityError se o nome já existir."""
    erro = validar_senha(senha)
    if erro:
        raise ValueError(erro)
    cur = con.execute(
        "INSERT INTO usuarios (nome, senha_hash, criado_em) VALUES (?, ?, ?)", (nome, hash_senha(senha), agora_iso())
    )
    return cur.lastrowid


def redefinir_senha(con: sqlite3.Connection, nome: str, senha: str) -> bool:
    """Troca a senha e derruba as sessões abertas desse usuário. False se o nome não existe."""
    erro = validar_senha(senha)
    if erro:
        raise ValueError(erro)
    with transacao(con):
        linha = con.execute("SELECT id FROM usuarios WHERE nome = ?", (nome,)).fetchone()
        if linha is None:
            return False
        con.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (hash_senha(senha), linha["id"]))
        con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (linha["id"],))
    return True


def criar_token(con: sqlite3.Connection, usuario_id: int, rotulo: str | None = None) -> tuple[int, str]:
    """Gera um token de API novo. Devolve (id, token em texto puro): é a única vez que o
    texto puro existe aqui; no banco fica só o hash."""
    token = "td_" + secrets.token_urlsafe(32)
    cur = con.execute(
        "INSERT INTO tokens_api (usuario_id, token_hash, rotulo, criado_em) VALUES (?, ?, ?, ?)",
        (usuario_id, hash_token(token), rotulo or None, agora_iso()),
    )
    return cur.lastrowid, token
