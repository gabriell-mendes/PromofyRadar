"""Autenticação: duas credenciais separadas, cada uma para um tipo de cliente.

- Token de API (header `Authorization: Bearer ...`): para os PCs, só em /api/ingest.
- Cookie de sessão (`td_sessao`): para o administrador no navegador, depois do login.

Um token vazado não abre o painel; um cookie roubado não envia ofertas como PC.
"""

import hashlib
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request

from .db import agora_iso, get_con, hash_token

COOKIE = "td_sessao"
SESSAO_DIAS = 7


# ---------- token de API (PCs) ----------
def usuario_atual(authorization: str = Header(default=""), con: sqlite3.Connection = Depends(get_con)) -> sqlite3.Row:
    esquema, _, token = authorization.partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Token ausente. Envie 'Authorization: Bearer <token>'.")
    usuario = con.execute(
        "SELECT u.id, u.nome FROM tokens_api t JOIN usuarios u ON u.id = t.usuario_id "
        "WHERE t.token_hash = ? AND t.revogado_em IS NULL",
        (hash_token(token.strip()),),
    ).fetchone()
    if usuario is None:
        raise HTTPException(status_code=401, detail="Token inválido ou revogado.")
    return usuario


# ---------- sessão por cookie (administradores) ----------
def _hash_sessao(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


def criar_sessao(con: sqlite3.Connection, usuario_id: int) -> str:
    """Abre uma sessão e devolve o valor que vai no cookie (no banco fica só o hash)."""
    valor = secrets.token_urlsafe(32)
    agora = datetime.now(timezone.utc)
    con.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora.isoformat(timespec="seconds"),))  # faxina
    con.execute(
        "INSERT INTO sessoes (id_hash, usuario_id, criado_em, expira_em) VALUES (?, ?, ?, ?)",
        (
            _hash_sessao(valor),
            usuario_id,
            agora.isoformat(timespec="seconds"),
            (agora + timedelta(days=SESSAO_DIAS)).isoformat(timespec="seconds"),
        ),
    )
    return valor


def encerrar_sessao(con: sqlite3.Connection, valor: str | None) -> None:
    if valor:
        con.execute("DELETE FROM sessoes WHERE id_hash = ?", (_hash_sessao(valor),))


def usuario_da_sessao(con: sqlite3.Connection, valor: str | None) -> sqlite3.Row | None:
    if not valor:
        return None
    return con.execute(
        "SELECT u.id, u.nome FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.id_hash = ? AND s.expira_em > ?",
        (_hash_sessao(valor), agora_iso()),
    ).fetchone()


def admin_logado(request: Request, con: sqlite3.Connection = Depends(get_con)) -> sqlite3.Row:
    """Rotas da API para administradores: sem sessão válida, 401."""
    usuario = usuario_da_sessao(con, request.cookies.get(COOKIE))
    if usuario is None:
        raise HTTPException(status_code=401, detail="Faça login.")
    return usuario


def somente_painel(x_techdrop: str = Header(default="")):
    """Proteção CSRF das rotas que usam cookie. O navegador envia cookie sozinho até em
    requisição disparada por outro site; mas outro site não consegue colocar este header
    (exigiria permissão CORS, que não damos). Mesmo padrão do painel local."""
    if x_techdrop != "1":
        raise HTTPException(status_code=403, detail="Requisição não permitida.")


# ---------- limite de tentativas de login ----------
class LimiteLogin:
    """Bloqueia o nome após muitas senhas erradas seguidas. Fica na memória do processo
    (suficiente para um servidor com um processo só). Troca o risco de adivinhar a senha
    pelo incômodo de um administrador ficar alguns minutos sem entrar."""

    def __init__(self, max_falhas: int = 5, janela_s: int = 600):
        self.max_falhas = max_falhas
        self.janela_s = janela_s
        self._falhas: dict[str, list[float]] = {}

    def _recentes(self, nome: str) -> list[float]:
        corte = time.monotonic() - self.janela_s
        recentes = [t for t in self._falhas.get(nome.lower(), []) if t > corte]
        if recentes:
            self._falhas[nome.lower()] = recentes
        else:
            self._falhas.pop(nome.lower(), None)
        return recentes

    def bloqueado(self, nome: str) -> bool:
        return len(self._recentes(nome)) >= self.max_falhas

    def falhou(self, nome: str) -> None:
        if len(self._falhas) > 1000:  # nomes inventados não podem encher a memória
            self._falhas.clear()
        self._falhas.setdefault(nome.lower(), []).append(time.monotonic())

    def acertou(self, nome: str) -> None:
        self._falhas.pop(nome.lower(), None)
