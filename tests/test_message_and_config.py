from datetime import datetime
from decimal import Decimal

import pytest

from app import config
from app.config import get_source
from app.message import format_price, generate_message
from app.models import Product, ReviewItem
from app.sources.mercadolivre import MercadoLivreSource
from app.sources.mercadolivre_scraper import MercadoLivreScraperSource
from app.sources.shopee import ShopeeSource


@pytest.fixture(autouse=True)
def limpar_cache_de_fontes():
    """get_source() cacheia uma instância por nome (ver app/config.py —
    necessário pro rate limit da fonte funcionar de verdade entre
    chamadas). Sem limpar entre testes, um teste poderia herdar a
    instância (e o estado interno dela) criada por outro teste.
    """
    config._INSTANCIAS.clear()
    yield
    config._INSTANCIAS.clear()


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


def test_get_source_padrao_e_mercadolivre_scraper():
    # Padrão mudou pra Mercado Livre via scraping (2026-09-16): funciona
    # sem credencial, ao contrário da Shopee — ver docs/decisao-fonte-de-dados.md.
    assert isinstance(get_source(), MercadoLivreScraperSource)


def test_get_source_por_nome():
    assert isinstance(get_source("shopee"), ShopeeSource)
    # API oficial do Mercado Livre, mantida só como referência histórica
    # (ver app/config.py) — chave separada de "mercadolivre" de propósito.
    assert isinstance(get_source("mercadolivre_api"), MercadoLivreSource)


def test_get_source_reaproveita_a_mesma_instancia():
    """get_source() cacheia por nome — ver o comentário em app/config.py.
    Existe pra MercadoLivreScraperSource conseguir respeitar
    MERCADOLIVRE_MIN_INTERVAL_SECONDS de verdade entre buscas na
    dashboard: se uma instância nova fosse criada a cada chamada, o
    rate limit nunca teria efeito nenhum.
    """
    assert get_source("shopee") is get_source("shopee")


def test_get_source_nome_desconhecido_levanta_erro_claro():
    with pytest.raises(ValueError, match="Disponíveis"):
        get_source("loja-que-nao-existe")
