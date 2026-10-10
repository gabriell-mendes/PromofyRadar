"""Etapa 7 (parte local): dois PCs, tokens diferentes, o mesmo produto, preços diferentes.

Um cenário só, do começo ao fim, como vai acontecer no VPS: cada pessoa envia do
próprio PC (token) e olha o painel pelo navegador (cookie de sessão).
"""

import pytest

# Mesmo produto (MLB25171538), links diferentes: o PC da Ana veio de um anúncio
# (pdp_filters), o da Bia de uma busca (searchVariation). A chave é a mesma.
LINK_ANA = "https://www.mercadolivre.com.br/produto-x/p/MLB25171538?pdp_filters=deal%3AMLB779362-1"
LINK_BIA = "https://www.mercadolivre.com.br/produto-x/p/MLB25171538?searchVariation=123"
LINK_OUTRO = "https://www.mercadolivre.com.br/produto-y/p/MLB99999999"


def oferta(url, preco, **extra):
    return {"loja": "mercadolivre", "url": url, "titulo": "Produto X", "preco": preco, **extra}


def enviar(pc, token, *ofertas):
    r = pc.post("/api/ingest", json={"ofertas": list(ofertas)}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def dois_pcs(painel):
    painel.admin("ana")
    painel.admin("bia")
    # Dois clientes sem cookie = dois PCs, cada um só com o seu token.
    return painel, (painel.cliente(), painel.token("ana", "PC da Ana")), (painel.cliente(), painel.token("bia", "PC da Bia"))


def test_dois_pcs_enviam_o_mesmo_produto_com_precos_diferentes(dois_pcs):
    painel, (pc_ana, token_ana), (pc_bia, token_bia) = dois_pcs

    # 1. O PC da Ana envia primeiro (e uma segunda oferta, só dela).
    r = enviar(pc_ana, token_ana, oferta(LINK_ANA, 100.0), oferta(LINK_OUTRO, 50.0))
    assert (r["criadas"], r["atualizadas"], r["ignoradas"]) == (2, 0, 0)

    # 2. O PC da Bia envia o mesmo produto, link diferente, preço menor, e tenta
    #    forjar o autor no corpo. Não duplica, é uma atualização.
    r = enviar(pc_bia, token_bia, oferta(LINK_BIA, 90.0, enviado_por="ana"))
    assert (r["criadas"], r["atualizadas"], r["ignoradas"]) == (0, 1, 0)

    # 3. Pelo banco: uma linha por produto, e o histórico guarda os dois preços,
    #    cada um com o autor certo (vindo do token, nunca do corpo).
    assert painel.con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 2
    historico = painel.con.execute(
        "SELECT p.preco, u.nome FROM precos p JOIN ofertas o ON o.id = p.oferta_id "
        "JOIN usuarios u ON u.id = p.enviado_por WHERE o.id_produto = 'MLB25171538' ORDER BY p.id"
    ).fetchall()
    assert [(h["preco"], h["nome"]) for h in historico] == [(100.0, "ana"), (90.0, "bia")]

    # 4. Pelo painel (cookie): cada administrador vê as mesmas 2 ofertas, juntas.
    for quem in ("ana", "bia"):
        dados = painel.entrar(quem).get("/api/ofertas").json()
        assert dados["total"] == 2
        produto = next(o for o in dados["ofertas"] if o["id_produto"] == "MLB25171538")
        assert produto["preco"] == 90.0  # vale o último envio
        assert produto["n_precos"] == 2  # mas o histórico guardou os dois
        assert produto["enviado_por"] == "bia"  # quem enviou o valor atual, e não "ana" do corpo forjado
        outro = next(o for o in dados["ofertas"] if o["id_produto"] == "MLB99999999")
        assert (outro["preco"], outro["n_precos"], outro["enviado_por"]) == (50.0, 1, "ana")


def test_reenviar_o_mesmo_lote_nao_duplica_e_so_aumenta_o_historico(dois_pcs):
    painel, (pc_ana, token_ana), _ = dois_pcs
    for _ in range(3):
        enviar(pc_ana, token_ana, oferta(LINK_ANA, 100.0))
    assert painel.con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 1
    assert painel.con.execute("SELECT COUNT(*) FROM precos").fetchone()[0] == 3


def test_descarte_de_uma_pessoa_vale_para_o_outro_pc(dois_pcs):
    painel, (pc_ana, token_ana), (pc_bia, token_bia) = dois_pcs
    enviar(pc_ana, token_ana, oferta(LINK_ANA, 100.0))

    # A Bia descarta no painel; depois a Ana reenvia do PC dela (com outro link do mesmo produto).
    bia = painel.entrar("bia")
    oferta_id = bia.get("/api/ofertas").json()["ofertas"][0]["id"]
    assert bia.post("/api/descartar", json={"ids": [oferta_id]}).json()["descartadas"] == 1

    r = enviar(pc_ana, token_ana, oferta(LINK_BIA, 80.0))
    assert (r["criadas"], r["atualizadas"], r["ignoradas"]) == (0, 0, 1)
    assert r["detalhes_ignoradas"][0]["motivo"] == "produto descartado no painel"
    assert painel.con.execute("SELECT COUNT(*) FROM precos").fetchone()[0] == 1


def test_sem_login_o_painel_redireciona_e_a_api_recusa(dois_pcs):
    painel, (pc_ana, token_ana), _ = dois_pcs
    enviar(pc_ana, token_ana, oferta(LINK_ANA, 100.0))

    visitante = painel.cliente()
    for caminho in ("/", "/tokens"):
        r = visitante.get(caminho, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
    assert visitante.get("/api/ofertas").status_code == 401


def test_as_duas_credenciais_nao_se_misturam(dois_pcs):
    painel, (pc_ana, token_ana), _ = dois_pcs
    ana = painel.entrar("ana")

    # Token de API só envia: não abre o painel.
    assert pc_ana.get("/api/ofertas", headers={"Authorization": f"Bearer {token_ana}"}).status_code == 401
    # Cookie só administra: não serve para enviar ofertas.
    r = ana.post("/api/ingest", json={"ofertas": [oferta(LINK_ANA, 100.0)]})
    assert r.status_code == 401
    assert painel.con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 0
