from datetime import datetime
from decimal import Decimal

from app.models import Product
from app.scoring import calcular_deal_score, gerar_motivo


def _produto(price, **kwargs):
    defaults = dict(
        source="shopee",
        source_id="1",
        title="Produto teste",
        url="https://exemplo.com/1",
        store="Loja teste",
        collected_at=datetime(2026, 1, 1),
    )
    defaults.update(kwargs)
    return Product(price=Decimal(str(price)), **defaults)


def test_desconto_valido_gera_score_alto():
    produto = _produto(80)
    precos = [Decimal("80"), Decimal("100"), Decimal("120")]
    score = calcular_deal_score(produto, precos)
    assert score > 50
    assert "abaixo da mediana" in gerar_motivo(produto, precos)


def test_preco_acima_da_mediana_gera_score_baixo():
    produto = _produto(150)
    precos = [Decimal("80"), Decimal("100"), Decimal("120")]
    score = calcular_deal_score(produto, precos)
    assert score < 50
    assert "acima da mediana" in gerar_motivo(produto, precos)


def test_produto_sem_grupo_para_comparar_recebe_nota_neutra():
    produto = _produto(100)
    score = calcular_deal_score(produto, [Decimal("100")])
    assert score == 50
    assert "sem grupo pra comparar" in gerar_motivo(produto, [Decimal("100")])


def test_preco_invalido_recebe_score_zero():
    produto = _produto(0)
    precos = [Decimal("0"), Decimal("100")]
    assert calcular_deal_score(produto, precos) == 0
    assert "inválido" in gerar_motivo(produto, precos)


def test_sem_vendas_penaliza_o_score():
    com_vendas = _produto(80, sales=50)
    sem_vendas = _produto(80, sales=0)
    precos = [Decimal("80"), Decimal("100"), Decimal("120")]

    score_com = calcular_deal_score(com_vendas, precos)
    score_sem = calcular_deal_score(sem_vendas, precos)

    assert score_sem < score_com
    assert "sem vendas registradas" in gerar_motivo(sem_vendas, precos)


def test_score_nunca_sai_do_intervalo_0_100():
    produto_muito_barato = _produto(1)
    precos = [Decimal("1"), Decimal("1000")]
    assert 0 <= calcular_deal_score(produto_muito_barato, precos) <= 100
