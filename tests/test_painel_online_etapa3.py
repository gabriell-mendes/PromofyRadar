import getpass
import sqlite3

import pytest

from painel_online import cli
from painel_online.credenciais import hash_senha, validar_senha, verificar_senha
from painel_online.db import conectar, criar_usuario, redefinir_senha

from conftest import SENHA

OFERTA = {"loja": "mercadolivre", "url": "https://www.mercadolivre.com.br/x/p/MLB25171538", "titulo": "Produto", "preco": 10.0}


@pytest.fixture
def p(painel):
    painel.admin("ana")
    painel.admin("bia")
    return painel


def cookie_de(cliente) -> str:
    return cliente.cookies.get("td_sessao")


# ---------- senhas ----------
def test_regras_de_senha():
    assert validar_senha("curta") is not None
    assert validar_senha("a" * 73) is not None
    assert validar_senha("uma senha boa de verdade") is None


def test_senha_fica_em_hash_bcrypt(p):
    guardado = p.con.execute("SELECT senha_hash FROM usuarios WHERE nome = 'ana'").fetchone()[0]
    assert guardado.startswith("$2") and SENHA not in guardado
    assert verificar_senha(SENHA, guardado) and not verificar_senha("outra-senha-qualquer", guardado)
    assert not verificar_senha(SENHA, None)  # usuário inexistente nunca autentica


def test_nome_duplicado_e_senha_fraca_sao_recusados(p):
    with pytest.raises(sqlite3.IntegrityError):
        criar_usuario(p.con, "ana", SENHA)
    with pytest.raises(ValueError):
        criar_usuario(p.con, "nova", "curta")


# ---------- login ----------
def test_login_define_cookie_seguro_e_abre_sessao(p):
    c = p.cliente()
    r = c.post("/api/login", json={"nome": "ana", "senha": SENHA})
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=lax" in set_cookie
    assert c.get("/api/eu").json() == {"nome": "ana"}


def test_cookie_nao_fica_em_texto_puro_no_banco(p):
    c = p.entrar("ana")
    hashes = [r[0] for r in p.con.execute("SELECT id_hash FROM sessoes")]
    assert cookie_de(c) not in hashes and all(len(h) == 64 for h in hashes)


def test_senha_errada_e_usuario_inexistente_dao_a_mesma_resposta(p):
    c = p.cliente()
    a = c.post("/api/login", json={"nome": "ana", "senha": "errada-errada"})
    b = c.post("/api/login", json={"nome": "ninguem", "senha": "errada-errada"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    assert c.get("/api/eu").status_code == 401


def test_login_sem_header_anti_csrf_e_barrado(p):
    r = p.cliente(com_header=False).post("/api/login", json={"nome": "ana", "senha": SENHA})
    assert r.status_code == 403


def test_muitas_senhas_erradas_bloqueiam_o_nome(p):
    c = p.cliente()
    for _ in range(5):
        assert c.post("/api/login", json={"nome": "ana", "senha": "errada-errada"}).status_code == 401
    # agora nem a senha certa entra, até a janela passar
    assert c.post("/api/login", json={"nome": "ana", "senha": SENHA}).status_code == 429
    # outra pessoa não é afetada
    assert c.post("/api/login", json={"nome": "bia", "senha": SENHA}).status_code == 200


def test_login_certo_zera_o_contador(p):
    c = p.cliente()
    for _ in range(4):
        c.post("/api/login", json={"nome": "ana", "senha": "errada-errada"})
    assert c.post("/api/login", json={"nome": "ana", "senha": SENHA}).status_code == 200
    for _ in range(4):
        assert c.post("/api/login", json={"nome": "ana", "senha": "errada-errada"}).status_code == 401


# ---------- sessão, logout, expiração ----------
def test_rotas_sem_login(p):
    c = p.cliente()
    for caminho in ("/api/eu", "/api/ofertas", "/api/tokens"):
        assert c.get(caminho).status_code == 401
    for caminho in ("/", "/tokens"):
        r = c.get(caminho, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
    assert c.get("/login").status_code == 200


def test_logado_ve_as_paginas_e_login_redireciona_para_a_home(p):
    c = p.entrar("ana")
    for caminho in ("/", "/tokens"):
        r = c.get(caminho)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert c.get("/login", follow_redirects=False).headers["location"] == "/"


def test_logout_invalida_a_sessao_no_servidor(p):
    c = p.entrar("ana")
    valor = cookie_de(c)
    assert c.post("/api/logout").status_code == 200
    # mesmo quem guardou o cookie antigo não entra mais
    ladrao = p.cliente()
    ladrao.cookies.set("td_sessao", valor)
    assert ladrao.get("/api/eu").status_code == 401


def test_sessao_expirada_nao_vale(p):
    c = p.entrar("ana")
    p.con.execute("UPDATE sessoes SET expira_em = '2000-01-01T00:00:00+00:00'")
    assert c.get("/api/eu").status_code == 401


def test_redefinir_senha_derruba_sessoes(p):
    c = p.entrar("ana")
    assert redefinir_senha(p.con, "ana", "outra-senha-bem-longa") is True
    assert c.get("/api/eu").status_code == 401
    assert p.cliente().post("/api/login", json={"nome": "ana", "senha": SENHA}).status_code == 401
    assert p.cliente().post("/api/login", json={"nome": "ana", "senha": "outra-senha-bem-longa"}).status_code == 200
    assert redefinir_senha(p.con, "ninguem", "outra-senha-bem-longa") is False


# ---------- cookie e token são coisas separadas ----------
def test_post_com_cookie_exige_header_anti_csrf(p):
    c = p.entrar("ana")
    assert c.post("/api/descartar", json={"ids": [1]}, headers={"X-TechDrop": ""}).status_code == 403
    assert c.post("/api/tokens", json={}, headers={"X-TechDrop": ""}).status_code == 403


def test_cookie_nao_serve_para_enviar_ofertas(p):
    c = p.entrar("ana")
    assert c.post("/api/ingest", json={"ofertas": [OFERTA]}).status_code == 401


def test_token_nao_serve_para_ver_ofertas_nem_gerenciar_tokens(p):
    token = p.token("ana")
    c = p.cliente()
    h = {"Authorization": f"Bearer {token}"}
    assert c.get("/api/ofertas", headers=h).status_code == 401
    assert c.get("/api/tokens", headers=h).status_code == 401
    assert c.post("/api/descartar", json={"ids": [1]}, headers=h).status_code == 401
    assert c.post("/api/ingest", json={"ofertas": [OFERTA]}, headers=h).status_code == 200


# ---------- tokens do próprio usuário ----------
def test_gerar_listar_usar_e_revogar_token(p):
    ana, pc = p.entrar("ana"), p.cliente()
    r = ana.post("/api/tokens", json={"rotulo": "PC do Gabriel"})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    token, token_id = r.json()["token"], r.json()["id"]
    assert token.startswith("td_")

    # a lista nunca devolve o token em texto puro
    lista = ana.get("/api/tokens").json()["tokens"]
    assert [t["rotulo"] for t in lista] == ["PC do Gabriel"] and token not in str(lista)
    assert token not in [x[0] for x in p.con.execute("SELECT token_hash FROM tokens_api")]

    h = {"Authorization": f"Bearer {token}"}
    assert pc.post("/api/ingest", json={"ofertas": [OFERTA]}, headers=h).json()["criadas"] == 1

    assert ana.post(f"/api/tokens/{token_id}/revogar").status_code == 200
    assert pc.post("/api/ingest", json={"ofertas": [OFERTA]}, headers=h).status_code == 401
    assert ana.get("/api/tokens").json()["tokens"][0]["revogado_em"] is not None
    assert ana.post(f"/api/tokens/{token_id}/revogar").status_code == 404  # já revogado


def test_ninguem_ve_nem_revoga_token_de_outra_pessoa(p):
    ana, bia = p.entrar("ana"), p.entrar("bia")
    token_id = ana.post("/api/tokens", json={"rotulo": "da ana"}).json()["id"]
    assert bia.get("/api/tokens").json()["tokens"] == []
    assert bia.post(f"/api/tokens/{token_id}/revogar").status_code == 404
    assert ana.get("/api/tokens").json()["tokens"][0]["revogado_em"] is None


def test_cabecalhos_de_seguranca(p):
    h = p.cliente().get("/login").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


# ---------- linha de comando ----------
def test_cli_criar_admin_e_redefinir(monkeypatch, tmp_path, capsys):
    db = tmp_path / "cli.db"
    monkeypatch.setenv("PAINEL_DB", str(db))
    monkeypatch.setattr("painel_online.credenciais.BCRYPT_ROUNDS", 4)
    senhas = iter([])
    monkeypatch.setattr(getpass, "getpass", lambda _="": next(senhas))

    senhas = iter([SENHA, SENHA])
    assert cli.main(["x", "criar-admin", "gabriel"]) == 0
    con = conectar(db)
    assert con.execute("SELECT senha_hash FROM usuarios WHERE nome = 'gabriel'").fetchone()[0].startswith("$2")

    senhas = iter([SENHA, SENHA])
    assert cli.main(["x", "criar-admin", "gabriel"]) == 1  # já existe
    senhas = iter(["curta", "curta"])
    assert cli.main(["x", "criar-admin", "novo"]) == 1  # senha fraca
    senhas = iter([SENHA, "diferente-da-outra"])
    assert cli.main(["x", "criar-admin", "novo"]) == 1  # confirmação não confere
    senhas = iter(["outra-senha-bem-longa"] * 2)
    assert cli.main(["x", "redefinir-senha", "gabriel"]) == 0
    senhas = iter([SENHA, SENHA])
    assert cli.main(["x", "redefinir-senha", "fantasma"]) == 1
    assert cli.main(["x"]) == 1
    con.close()
