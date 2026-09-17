"""Testes de app/collect.py: a regra de decidir se uma oferta merece ser
reportada de novo (_deveria_reportar), isolada de rede e de banco de
dados de verdade -- ver tests/test_storage.py pra persistência em si,
este arquivo testa só a REGRA de cima, com um "existente" fabricado à
mão em vez de vir do banco.
"""

from datetime import datetime
from decimal import Decimal

from app.collect import _deveria_reportar
from app.models import Product


def _produto(price, original_price=None) -> Product:
    return Product(
        source="mercadolivre",
        source_id="MLB1",
        title="Produto",
        price=Decimal(str(price)),
        original_price=Decimal(str(original_price)) if original_price is not None else None,
        url="https://produto.mercadolivre.com.br/MLB1",
        store="Loja",
        collected_at=datetime(2026, 1, 1),
    )


def _existente(price, desconto):
    return {"price": Decimal(str(price)), "desconto_percentual": desconto}


def test_primeira_vez_que_atinge_o_minimo_deve_reportar():
    produto = _produto(price=60, original_price=100)  # 40% off
    assert _deveria_reportar(produto, desconto_min=30, existente=None) is True


def test_nao_atinge_o_minimo_nunca_reporta_mesmo_sem_historico():
    produto = _produto(price=90, original_price=100)  # 10% off
    assert _deveria_reportar(produto, desconto_min=30, existente=None) is False


def test_mesmo_preco_e_desconto_de_antes_nao_reporta_de_novo():
    produto = _produto(price=60, original_price=100)  # 40% off
    existente = _existente(price=60, desconto=40.0)
    assert _deveria_reportar(produto, desconto_min=30, existente=existente) is False


def test_preco_mudou_mas_ainda_atinge_o_minimo_reporta_de_novo():
    produto = _produto(price=55, original_price=100)  # 45% off
    existente = _existente(price=60, desconto=40.0)
    assert _deveria_reportar(produto, desconto_min=30, existente=existente) is True


def test_deixou_de_atingir_o_minimo_nao_reporta():
    produto = _produto(price=85, original_price=100)  # 15% off
    existente = _existente(price=60, desconto=40.0)  # antes atingia
    assert _deveria_reportar(produto, desconto_min=30, existente=existente) is False


def test_volta_a_atingir_o_minimo_depois_de_ter_caido_reporta_de_novo():
    existente = _existente(price=85, desconto=15.0)  # estava abaixo do mínimo
    produto = _produto(price=60, original_price=100)  # 40% off agora
    assert _deveria_reportar(produto, desconto_min=30, existente=existente) is True
