from datetime import date, timedelta

from historico import chave_produto, obter, registrar

HOJE = date(2026, 9, 30)


def test_chave_usa_codigo_mlb_e_ignora_parametros_de_tracking():
    a = "https://www.mercadolivre.com.br/x/p/MLB43514990?pdp_filters=deal%3AMLB779362-1"
    b = "https://www.mercadolivre.com.br/x/p/MLB43514990#polycard_client=search"
    c = "https://produto.mercadolivre.com.br/MLB-7006107748-conjunto-_JM?searchVariation=1"
    assert chave_produto(a) == chave_produto(b) == "MLB43514990"
    assert chave_produto(c) == "MLB7006107748"


def test_chave_de_link_up_usa_mlbu_e_nao_o_id_da_promocao_da_query():
    # Dados reais: 5 produtos diferentes tinham o mesmo pdp_filters=deal:MLB779362-1
    a = "https://www.mercadolivre.com.br/mala-x/up/MLBU3367167774?pdp_filters=deal%3AMLB779362-1"
    b = "https://www.mercadolivre.com.br/monitor-y/up/MLBU5096633476?pdp_filters=deal%3AMLB779362-1"
    assert chave_produto(a) == "MLBU3367167774"
    assert chave_produto(b) == "MLBU5096633476"


def test_chave_sem_codigo_usa_link_sem_query():
    assert chave_produto("https://loja.com/produto?a=1#x") == "https://loja.com/produto"


def test_um_registro_por_dia_o_mais_recente_vence(tmp_path):
    db = tmp_path / "h.db"
    registrar([("p1", 100)], quando=HOJE - timedelta(days=1), db=db)
    registrar([("p1", 90)], quando=HOJE - timedelta(days=1), db=db)
    assert obter(["p1"], antes_de=HOJE, db=db) == {"p1": [90.0]}


def test_obter_nao_inclui_hoje_e_respeita_a_janela(tmp_path):
    db = tmp_path / "h.db"
    for d, preco in [(0, 50), (1, 100), (10, 110), (29, 120), (31, 999)]:
        registrar([("p1", preco)], quando=HOJE - timedelta(days=d), db=db)
    assert obter(["p1"], antes_de=HOJE, dias=30, db=db)["p1"] == [120.0, 110.0, 100.0]


def test_produto_desconhecido_volta_lista_vazia(tmp_path):
    assert obter(["nunca-visto"], antes_de=HOJE, db=tmp_path / "h.db") == {"nunca-visto": []}


def test_preco_invalido_nao_e_gravado(tmp_path):
    db = tmp_path / "h.db"
    assert registrar([("p1", 0), ("p2", -3)], quando=HOJE, db=db) == 0
