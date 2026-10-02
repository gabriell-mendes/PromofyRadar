import pytest

from painel_online import app as app_mod

LINK_A = "https://www.mercadolivre.com.br/produto-x/p/MLB25171538?pdp_filters=deal%3AMLB779362-1"
LINK_A2 = "https://www.mercadolivre.com.br/produto-x/p/MLB25171538?searchVariation=123"
LINK_B = "https://www.mercadolivre.com.br/produto-y/p/MLB99999999"


def oferta(url=LINK_A, preco=100.0, **extra):
    return {"loja": "mercadolivre", "url": url, "titulo": "Produto", "preco": preco, **extra}


@pytest.fixture
def ctx(painel):
    """PCs enviam com token; administradores olham pela sessão (cookie)."""
    painel.admin("ana")
    painel.admin("bia")
    pc = painel.cliente()
    tokens = {"ana": painel.token("ana"), "bia": painel.token("bia")}
    return painel, pc, tokens


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def ingest(pc, token, *ofertas):
    return pc.post("/api/ingest", json={"ofertas": list(ofertas)}, headers=auth(token))


# ---------- autenticação do envio (token) ----------
def test_ingest_sem_token_ou_token_invalido_da_401(ctx):
    _, pc, _ = ctx
    assert pc.post("/api/ingest", json={"ofertas": [oferta()]}).status_code == 401
    assert ingest(pc, "td_errado", oferta()).status_code == 401


def test_token_revogado_da_401(ctx):
    p, pc, t = ctx
    p.con.execute("UPDATE tokens_api SET revogado_em = '2026-01-01'")
    assert ingest(pc, t["ana"], oferta()).status_code == 401


def test_banco_guarda_so_o_hash_do_token(ctx):
    p, _, t = ctx
    hashes = [r[0] for r in p.con.execute("SELECT token_hash FROM tokens_api")]
    assert t["ana"] not in hashes and all(len(h) == 64 for h in hashes)


# ---------- ingest ----------
def test_ingest_cria_depois_atualiza_e_guarda_historico(ctx):
    p, pc, t = ctx
    r = ingest(pc, t["ana"], oferta(LINK_A, 100.0), oferta(LINK_B, 50.0)).json()
    assert (r["criadas"], r["atualizadas"], r["ignoradas"]) == (2, 0, 0)

    # mesmo produto, query string diferente, preço novo, outra pessoa enviando
    r = ingest(pc, t["bia"], oferta(LINK_A2, 90.0)).json()
    assert (r["criadas"], r["atualizadas"], r["ignoradas"]) == (0, 1, 0)

    assert p.con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 2
    precos = p.con.execute(
        "SELECT p.preco, u.nome FROM precos p JOIN ofertas o ON o.id = p.oferta_id "
        "JOIN usuarios u ON u.id = p.enviado_por WHERE o.id_produto = 'MLB25171538' ORDER BY p.id"
    ).fetchall()
    assert [(x["preco"], x["nome"]) for x in precos] == [(100.0, "ana"), (90.0, "bia")]


def test_repetir_dentro_do_mesmo_lote_nao_duplica(ctx):
    p, pc, t = ctx
    r = ingest(pc, t["ana"], oferta(LINK_A), oferta(LINK_A2, 80.0)).json()
    assert (r["criadas"], r["atualizadas"]) == (1, 1)
    assert p.con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 1


def test_enviado_por_vem_do_token_nao_do_corpo(ctx):
    p, pc, t = ctx
    ingest(pc, t["ana"], oferta(enviado_por="bia"))
    ofertas = p.entrar("bia").get("/api/ofertas").json()["ofertas"]
    assert ofertas[0]["enviado_por"] == "ana"


def test_oferta_invalida_e_ignorada_sem_derrubar_o_lote(ctx):
    _, pc, t = ctx
    ruim = oferta(preco=-1)
    perigosa = oferta(LINK_B, imagem="javascript:alert(1)")
    r = ingest(pc, t["ana"], oferta(), ruim, perigosa).json()
    assert (r["criadas"], r["ignoradas"]) == (1, 2)
    assert {d["indice"] for d in r["detalhes_ignoradas"]} == {1, 2}


def test_limites_de_tamanho(ctx):
    _, pc, t = ctx
    muitas = [oferta(f"https://x.com/p/MLB{10000000 + i}") for i in range(501)]
    assert ingest(pc, t["ana"], *muitas).status_code == 422
    assert ingest(pc, t["ana"]).status_code == 422  # lista vazia
    gigante = oferta(titulo="x" * (app_mod.MAX_BYTES + 1))
    assert ingest(pc, t["ana"], gigante).status_code == 413


# ---------- listar, descartar, restaurar (administradores) ----------
def test_descartar_restaurar_e_reenvio_de_descartado(ctx):
    p, pc, t = ctx
    ana, bia = p.entrar("ana"), p.entrar("bia")
    ingest(pc, t["ana"], oferta(LINK_A), oferta(LINK_B))
    lista = ana.get("/api/ofertas").json()
    assert lista["total"] == 2
    id_a = next(o["id"] for o in lista["ofertas"] if o["id_produto"] == "MLB25171538")

    r = bia.post("/api/descartar", json={"ids": [id_a, 9999]}).json()
    assert (r["descartadas"], r["ignoradas"]) == (1, 1)
    assert ana.get("/api/ofertas").json()["total"] == 1  # descarte de uma pessoa vale para todas
    desc = ana.get("/api/ofertas?status=descartadas").json()
    assert desc["total"] == 1 and desc["ofertas"][0]["descartada"] is True

    # reenviar um produto descartado não o ressuscita
    r = ingest(pc, t["ana"], oferta(LINK_A2, 70.0)).json()
    assert (r["criadas"], r["atualizadas"], r["ignoradas"]) == (0, 0, 1)

    r = ana.post("/api/restaurar", json={"ids": [id_a]}).json()
    assert r["restauradas"] == 1
    assert ana.get("/api/ofertas").json()["total"] == 2


def test_lista_traz_campos_e_historico(ctx):
    p, pc, t = ctx
    ana = p.entrar("ana")
    ingest(pc, t["ana"], oferta(deal_score=80, deal_motivos=["abaixo da mediana"], deal_flags=["menor_preco_recente"]))
    o = ana.get("/api/ofertas").json()["ofertas"][0]
    assert o["deal_motivos"] == ["abaixo da mediana"] and o["deal_flags"] == ["menor_preco_recente"]

    # vale o último valor recebido (o painel online não recalcula o Deal Score)
    ingest(pc, t["ana"], oferta(LINK_A2, 95.0, deal_score=60))
    o = ana.get("/api/ofertas").json()["ofertas"][0]
    assert o["preco"] == 95.0 and o["deal_score"] == 60 and o["deal_motivos"] == []
    assert o["n_precos"] == 2
