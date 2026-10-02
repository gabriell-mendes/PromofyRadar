"""Painel online: recebe ofertas dos PCs, guarda, deduplica e exibe.

Dois tipos de credencial (ver auth.py):
- PCs: token de API, só em POST /api/ingest.
- Administradores: login com senha, cookie de sessão, para todo o resto.

Rodar na raiz do projeto (PAINEL_COOKIE_SECURE=0 só se for testar em http local):
    .venv\\Scripts\\python.exe -m uvicorn painel_online.app:app --port 8000
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    COOKIE,
    SESSAO_DIAS,
    LimiteLogin,
    admin_logado,
    criar_sessao,
    encerrar_sessao,
    somente_painel,
    usuario_atual,
    usuario_da_sessao,
)
from .credenciais import verificar_senha
from .db import agora_iso, caminho_db, conectar, criar_token, criar_tabelas, get_con, transacao
from .ingest import ingerir

PAGINAS_DIR = Path(__file__).resolve().parent / "paginas"
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BYTES = 1_000_000  # tamanho máximo do corpo de um POST
MAX_OFERTAS_POR_ENVIO = 500
SEM_CACHE = {"Cache-Control": "no-store"}  # páginas e respostas com dados de login não ficam em cache


class IngestIn(BaseModel):
    # Cada item é validado depois, um a um (OfertaIn): uma oferta ruim não derruba o lote.
    ofertas: list[Any] = Field(min_length=1, max_length=MAX_OFERTAS_POR_ENVIO)


class IdsIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=MAX_OFERTAS_POR_ENVIO)


class LoginIn(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    senha: str = Field(min_length=1, max_length=200)


class TokenIn(BaseModel):
    rotulo: str | None = Field(default=None, max_length=60)  # ex: "PC do Gabriel"


def criar_app(db_path: str | Path | None = None, cookie_secure: bool | None = None) -> FastAPI:
    app = FastAPI(title="TechDrop Painel Online")
    app.state.db_path = Path(db_path) if db_path else caminho_db()
    if cookie_secure is None:
        # Secure = o navegador só envia o cookie por HTTPS. Padrão ligado; desligue só em teste local.
        cookie_secure = os.environ.get("PAINEL_COOKIE_SECURE", "1") != "0"
    app.state.cookie_secure = cookie_secure
    app.state.limite_login = LimiteLogin()
    con = conectar(app.state.db_path)
    criar_tabelas(con)
    con.close()

    @app.middleware("http")
    async def protecoes(request: Request, call_next):
        # Barra corpo grande antes de ler. Proteção básica; o Caddy reforça no deploy (Etapa 5).
        if request.method in ("POST", "PUT", "PATCH"):
            tamanho = request.headers.get("content-length")
            if tamanho is None or not tamanho.isdigit():
                return JSONResponse({"detail": "Content-Length obrigatório."}, status_code=411)
            if int(tamanho) > MAX_BYTES:
                return JSONResponse({"detail": f"Corpo maior que {MAX_BYTES} bytes."}, status_code=413)
        resposta = await call_next(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Referrer-Policy"] = "same-origin"
        return resposta

    # ---------- páginas ----------
    def pagina(nome: str) -> FileResponse:
        return FileResponse(PAGINAS_DIR / nome, headers=SEM_CACHE)

    @app.get("/", include_in_schema=False)
    def pagina_inicial(request: Request, con: sqlite3.Connection = Depends(get_con)):
        if usuario_da_sessao(con, request.cookies.get(COOKIE)) is None:
            return RedirectResponse("/login", status_code=303)
        return pagina("index.html")

    @app.get("/tokens", include_in_schema=False)
    def pagina_tokens(request: Request, con: sqlite3.Connection = Depends(get_con)):
        if usuario_da_sessao(con, request.cookies.get(COOKIE)) is None:
            return RedirectResponse("/login", status_code=303)
        return pagina("tokens.html")

    @app.get("/login", include_in_schema=False)
    def pagina_login(request: Request, con: sqlite3.Connection = Depends(get_con)):
        if usuario_da_sessao(con, request.cookies.get(COOKIE)) is not None:
            return RedirectResponse("/", status_code=303)
        return pagina("login.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/saude")
    def saude(con: sqlite3.Connection = Depends(get_con)):
        """Sem login e sem dados: só diz que o painel e o banco respondem (para conferir o deploy)."""
        con.execute("SELECT 1")
        return {"ok": True}

    # ---------- login e logout (cookie) ----------
    @app.post("/api/login", dependencies=[Depends(somente_painel)])
    def login(dados: LoginIn, request: Request, con: sqlite3.Connection = Depends(get_con)):
        limite: LimiteLogin = request.app.state.limite_login
        if limite.bloqueado(dados.nome):
            raise HTTPException(status_code=429, detail="Muitas tentativas. Tente de novo em alguns minutos.")
        usuario = con.execute("SELECT id, senha_hash FROM usuarios WHERE nome = ?", (dados.nome,)).fetchone()
        if not verificar_senha(dados.senha, usuario["senha_hash"] if usuario else None):
            limite.falhou(dados.nome)
            # mesma mensagem para "usuário não existe" e "senha errada"
            raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")
        limite.acertou(dados.nome)
        valor = criar_sessao(con, usuario["id"])
        resposta = JSONResponse({"nome": dados.nome}, headers=SEM_CACHE)
        resposta.set_cookie(
            COOKIE,
            valor,
            max_age=SESSAO_DIAS * 86400,
            httponly=True,  # JavaScript da página não consegue ler o cookie (limita estrago de XSS)
            secure=request.app.state.cookie_secure,
            samesite="lax",  # não vai em POST disparado por outro site
            path="/",
        )
        return resposta

    @app.post("/api/logout", dependencies=[Depends(somente_painel)])
    def logout(request: Request, con: sqlite3.Connection = Depends(get_con)):
        encerrar_sessao(con, request.cookies.get(COOKIE))
        resposta = JSONResponse({"ok": True}, headers=SEM_CACHE)
        resposta.delete_cookie(COOKIE, path="/")
        return resposta

    @app.get("/api/eu")
    def eu(admin=Depends(admin_logado)):
        return {"nome": admin["nome"]}

    # ---------- tokens de API do próprio usuário ----------
    @app.get("/api/tokens")
    def listar_tokens(admin=Depends(admin_logado), con: sqlite3.Connection = Depends(get_con)):
        linhas = con.execute(
            "SELECT id, rotulo, criado_em, revogado_em FROM tokens_api WHERE usuario_id = ? ORDER BY id DESC",
            (admin["id"],),
        ).fetchall()
        return {"tokens": [dict(r) for r in linhas]}  # o token em si nunca é devolvido aqui

    @app.post("/api/tokens", dependencies=[Depends(somente_painel)])
    def gerar_token(dados: TokenIn, admin=Depends(admin_logado), con: sqlite3.Connection = Depends(get_con)):
        token_id, token = criar_token(con, admin["id"], (dados.rotulo or "").strip() or None)
        # Única resposta que contém o token em texto puro. Não pode ficar em cache.
        return JSONResponse({"id": token_id, "token": token, "rotulo": dados.rotulo}, headers=SEM_CACHE)

    @app.post("/api/tokens/{token_id}/revogar", dependencies=[Depends(somente_painel)])
    def revogar_token(token_id: int, admin=Depends(admin_logado), con: sqlite3.Connection = Depends(get_con)):
        # Filtra por usuario_id: ninguém revoga token de outra pessoa.
        cur = con.execute(
            "UPDATE tokens_api SET revogado_em = ? WHERE id = ? AND usuario_id = ? AND revogado_em IS NULL",
            (agora_iso(), token_id, admin["id"]),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Token não encontrado ou já revogado.")
        return {"ok": True}

    # ---------- envio dos PCs (token de API) ----------
    @app.post("/api/ingest")
    def ingest(dados: IngestIn, usuario=Depends(usuario_atual), con: sqlite3.Connection = Depends(get_con)):
        return ingerir(con, usuario["id"], dados.ofertas)

    # ---------- ofertas (administradores, cookie) ----------
    @app.get("/api/ofertas")
    def listar(
        status: Literal["ativas", "descartadas", "todas"] = "ativas",
        limite: int = Query(200, ge=1, le=1000),
        admin=Depends(admin_logado),
        con: sqlite3.Connection = Depends(get_con),
    ):
        filtro = {
            "ativas": "WHERE d.oferta_id IS NULL",
            "descartadas": "WHERE d.oferta_id IS NOT NULL",
            "todas": "",
        }[status]
        base = (
            "FROM ofertas o JOIN usuarios u ON u.id = o.enviado_por "
            f"LEFT JOIN descartados d ON d.oferta_id = o.id {filtro}"
        )
        total = con.execute(f"SELECT COUNT(*) {base}").fetchone()[0]
        linhas = con.execute(
            f"""SELECT o.*, u.nome AS enviado_por_nome, d.descartado_em,
                       (SELECT COUNT(*) FROM precos p WHERE p.oferta_id = o.id) AS n_precos
                {base}
                ORDER BY o.deal_score IS NULL, o.deal_score DESC, o.desconto DESC, o.id DESC
                LIMIT ?""",
            (limite,),
        ).fetchall()
        ofertas = []
        for r in linhas:
            o = dict(r)
            o["enviado_por"] = o.pop("enviado_por_nome")
            o["deal_motivos"] = json.loads(o["deal_motivos"])
            o["deal_flags"] = json.loads(o["deal_flags"])
            o["descartada"] = o["descartado_em"] is not None
            ofertas.append(o)
        return {"total": total, "ofertas": ofertas}

    @app.post("/api/descartar", dependencies=[Depends(somente_painel)])
    def descartar(dados: IdsIn, admin=Depends(admin_logado), con: sqlite3.Connection = Depends(get_con)):
        agora = agora_iso()
        feitas = 0
        with transacao(con):
            for oferta_id in dados.ids:
                # SELECT garante que só descarta id que existe; OR IGNORE pula quem já estava descartado.
                cur = con.execute(
                    "INSERT OR IGNORE INTO descartados (oferta_id, descartado_em, descartado_por) "
                    "SELECT id, ?, ? FROM ofertas WHERE id = ?",
                    (agora, admin["id"], oferta_id),
                )
                feitas += cur.rowcount
        return {"descartadas": feitas, "ignoradas": len(dados.ids) - feitas}

    @app.post("/api/restaurar", dependencies=[Depends(somente_painel)])
    def restaurar(dados: IdsIn, admin=Depends(admin_logado), con: sqlite3.Connection = Depends(get_con)):
        feitas = 0
        with transacao(con):
            for oferta_id in dados.ids:
                feitas += con.execute("DELETE FROM descartados WHERE oferta_id = ?", (oferta_id,)).rowcount
        return {"restauradas": feitas, "ignoradas": len(dados.ids) - feitas}

    return app


app = criar_app()
