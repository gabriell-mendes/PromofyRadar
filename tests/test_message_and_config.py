from datetime import datetime
from decimal import Decimal

import pytest

from app.config import get_source
from app.message import format_price, generate_message
from app.models import Product, ReviewItem
from app.sources.mercadolivre import MercadoLivreSource
from app.sources.shopee import ShopeeSource


def test_format_price_usa_virgula_brasileira():
    assert format_price(Decimal("1234.5")) == "R$ 1234,50"


def test_generate_message_usa_original_price_quando_existe():
    produto = Product(
        source="shopee",
        source_id="1",
        title="Produto X",
        price=Decimal("80"),
        original_price=Decimal("100"),
        url="https://exemplo.com/x",
        store="Loja X",
        collected_at=datetime(2026, 1, 1),
    )
    item = ReviewItem(product=produto, score=90, reason="motivo")
    msg = generate_message(item)
    assert "De R$ 100,00 por R$ 80,00" in msg
    assert "https://exemplo.com/x" in msg
    assert "Loja X" in msg


def test_generate_message_sem_original_price_usa_preco_atual_nos_dois_lados():
    produto = Product(
        source="shopee",
        source_id="2",
        title="Produto Y",
        price=Decimal("50"),
        url="https://exemplo.com/y",
        store="Loja Y",
        collected_at=datetime(2026, 1, 1),
    )
    item = ReviewItem(product=produto, score=50, reason="motivo")
    msg = generate_message(item)
    assert "De R$ 50,00 por R$ 50,00" in msg


def test_get_source_padrao_e_shopee():
    assert isinstance(get_source(), ShopeeSource)


def test_get_source_por_nome():
    assert isinstance(get_source("mercadolivre"), MercadoLivreSource)


def test_get_source_nome_desconhecido_levanta_erro_claro():
    with pytest.raises(ValueError, match="Disponíveis"):
        get_source("loja-que-nao-existe")
