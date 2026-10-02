import pytest

from deal_score import (
    avaliar,
    calcular_desconto_real,
    faixa,
    nota_desconto,
    nota_minimo,
)

GRUPO = [300, 310, 295, 290, 305, 320, 280]  # mediana 300


def test_desconto_real_e_nota():
    assert calcular_desconto_real(210, 300) == pytest.approx(0.30)
    assert calcular_desconto_real(330, 300) == pytest.approx(-0.10)
    assert calcular_desconto_real(100, 0) == 0.0
    assert nota_desconto(0) == 0
    assert nota_desconto(0.15) == pytest.approx(0.5)
    assert nota_desconto(0.30) == 1
    assert nota_desconto(0.50) == 1      # trava no teto
    assert nota_desconto(-0.20) == 0     # preco acima da referencia nao vira nota negativa


def test_nota_minimo():
    assert nota_minimo(90, 100) == 1.0   # abaixo do menor recente
    assert nota_minimo(100, 100) == 1.0
    assert nota_minimo(107.5, 100) == pytest.approx(0.5)
    assert nota_minimo(130, 100) == 0.0


def test_preco_invalido_nao_recebe_nota():
    for preco in (0, -5, None):
        r = avaliar(preco, None, GRUPO, [300] * 10)
        assert r["score"] is None
        assert "preco_invalido" in r["flags"]


def test_sem_historico_e_sem_grupo_suficiente_nao_ha_nota():
    r = avaliar(200, None, [300, 310], [])
    assert r["score"] is None
    assert r["confianca"] == "nenhuma"


def test_so_grupo_da_confianca_baixa_e_usa_100_por_cento_do_peso():
    r = avaliar(210, None, GRUPO, [])      # 30% abaixo da mediana do grupo
    assert r["score"] == 100
    assert r["confianca"] == "baixa"


def test_historico_curto_demais_e_ignorado():
    r = avaliar(210, None, GRUPO, [300, 300])   # so 2 dias, minimo e 3
    assert r["confianca"] == "baixa"
    assert "menor_preco_recente" not in r["flags"]


def test_historico_da_confianca_alta_e_premia_desconto_real():
    r = avaliar(210, 300, GRUPO, [300] * 10)
    assert r["confianca"] == "alta"
    assert r["score"] >= 95
    assert "menor_preco_recente" in r["flags"]


def test_preco_estavel_no_proprio_minimo_nao_ganha_pontos():
    r = avaliar(300, None, GRUPO, [300] * 10)
    assert r["score"] == 0


def test_preco_acima_do_historico_fica_com_zero():
    r = avaliar(360, None, GRUPO, [280] * 10)
    assert r["score"] == 0


def test_desconto_anunciado_nunca_soma_pontos():
    sem = avaliar(260, None, GRUPO, [300] * 10)
    com = avaliar(260, 900, GRUPO, [300] * 10)   # loja grita "de R$ 900"
    assert sem["score"] == com["score"]


def test_desconto_inflado_e_acusado_com_historico():
    r = avaliar(290, 480, GRUPO, [290] * 10)
    assert "desconto_inflado" in r["flags"]
    assert r["score"] < 10


def test_desconto_anunciado_coerente_nao_e_inflado():
    r = avaliar(240, 300, GRUPO, [300] * 10)     # "de 300" bate com o historico
    assert "desconto_inflado" not in r["flags"]


def test_desconto_inflado_exige_historico_para_provar():
    r = avaliar(290, 480, GRUPO, [])
    assert "desconto_inflado" not in r["flags"]


def test_faixas():
    assert faixa(None) == "Sem nota"
    assert faixa(100) == "Ótima"
    assert faixa(75) == "Ótima"
    assert faixa(74) == "Boa"
    assert faixa(50) == "Boa"
    assert faixa(25) == "Regular"
    assert faixa(0) == "Fraca"
