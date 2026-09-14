"""Testes do collector Shopee: resposta válida, vazia, erro HTTP, timeout,
produto sem preço, duplicado e dados incompletos (via comportamento comum
da base, já coberto em test_base_source.py, mas exercitado aqui com o
formato real de item da Shopee) — mais normalização de preço/desconto/
URL/ID/título.

Nenhum destes testes faz uma chamada de rede real: requests.post é sempre
mockado, porque não há credenciais reais neste ambiente (ver docstring de
app/sources/shopee.py).
"""

from unittest.mock import Mock, patch

import pytest
import requests

from app.sources.base import OfferSourceError
from app.sources.shopee import ShopeeSource


def _fonte():
    return ShopeeSource(app_id="id-teste", app_secret="secret-teste")


def _resposta_graphql(nodes):
    resposta = Mock()
    resposta.status_code = 200
    resposta.content = b"{}"
    resposta.raise_for_status = Mock()
    resposta.json = Mock(return_value={"data": {"productOfferV2": {"nodes": nodes}}})
    return resposta


ITEM_VALIDO = {
    "itemId": 111,
    "productName": "Fone Bluetooth XYZ",
    "imageUrl": "https://img.exemplo.com/1.jpg",
    "offerLink": "https://shopee.com.br/produto-1",
    "price": "99.90",
    "priceMin": "99.90",
    "priceMax": "149.90",
    "priceDiscountRate": 33,
    "sales": 1200,
    "shopName": "Loja Exemplo",
}


def test_credenciais_ausentes_gera_erro_claro():
    fonte = ShopeeSource(app_id=None, app_secret=None)
    with pytest.raises(OfferSourceError, match="SHOPEE_APP_ID"):
        fonte.buscar_produtos_raw("notebook")


@patch("app.sources.shopee.requests.post")
def test_resposta_valida_e_normalizada_corretamente(mock_post):
    mock_post.return_value = _resposta_graphql([ITEM_VALIDO])
    fonte = _fonte()

    produtos = fonte.buscar_produtos("fone bluetooth")

    assert len(produtos) == 1
    p = produtos[0]
    assert p.source == "shopee"
    assert p.source_id == "111"
    assert p.title == "Fone Bluetooth XYZ"
    assert str(p.price) == "99.90"
    assert str(p.original_price) == "149.90"
    assert p.url == "https://shopee.com.br/produto-1"
    assert p.image_url == "https://img.exemplo.com/1.jpg"
    assert p.store == "Loja Exemplo"
    assert p.sales == 1200


@patch("app.sources.shopee.requests.post")
def test_resposta_vazia_nao_quebra(mock_post):
    mock_post.return_value = _resposta_graphql([])
    assert _fonte().buscar_produtos("query sem resultado") == []


@patch("app.sources.shopee.requests.post")
def test_erro_http_vira_offer_source_error(mock_post):
    resposta = Mock()
    resposta.status_code = 500
    resposta.content = b"erro interno"
    resposta.text = "erro interno"
    resposta.raise_for_status = Mock(side_effect=requests.HTTPError("500"))
    mock_post.return_value = resposta

    with pytest.raises(OfferSourceError):
        _fonte().buscar_produtos_raw("notebook")


@patch("app.sources.shopee.requests.post")
def test_timeout_vira_offer_source_error(mock_post):
    mock_post.side_effect = requests.Timeout("demorou demais")

    with pytest.raises(OfferSourceError, match="Timeout"):
        _fonte().buscar_produtos_raw("notebook")


@patch("app.sources.shopee.requests.post")
def test_rate_limit_vira_offer_source_error(mock_post):
    resposta = Mock()
    resposta.status_code = 429
    resposta.content = b'{"error":10030}'
    mock_post.return_value = resposta

    with pytest.raises(OfferSourceError, match="Rate limit"):
        _fonte().buscar_produtos_raw("notebook")


@patch("app.sources.shopee.requests.post")
def test_erro_graphql_vira_offer_source_error(mock_post):
    resposta = Mock()
    resposta.status_code = 200
    resposta.content = b"{}"
    resposta.raise_for_status = Mock()
    resposta.json = Mock(return_value={"errors": [{"message": "keyword inválido"}]})
    mock_post.return_value = resposta

    with pytest.raises(OfferSourceError, match="GraphQL"):
        _fonte().buscar_produtos_raw("notebook")


@patch("app.sources.shopee.requests.post")
def test_produto_sem_preco_e_descartado(mock_post):
    item_sem_preco = {**ITEM_VALIDO, "itemId": 222, "price": None}
    mock_post.return_value = _resposta_graphql([item_sem_preco, ITEM_VALIDO])

    produtos = _fonte().buscar_produtos("notebook")

    assert [p.source_id for p in produtos] == ["111"]


@patch("app.sources.shopee.requests.post")
def test_produto_sem_link_e_descartado(mock_post):
    item_sem_link = {**ITEM_VALIDO, "itemId": 333, "offerLink": None}
    mock_post.return_value = _resposta_graphql([item_sem_link])

    assert _fonte().buscar_produtos("notebook") == []


@patch("app.sources.shopee.requests.post")
def test_produto_duplicado_mantem_so_o_primeiro(mock_post):
    mock_post.return_value = _resposta_graphql([ITEM_VALIDO, ITEM_VALIDO])

    produtos = _fonte().buscar_produtos("notebook")

    assert len(produtos) == 1


def test_priceMax_igual_ao_preco_nao_vira_desconto_falso():
    item = {**ITEM_VALIDO, "priceMax": "99.90"}  # igual ao price, sem desconto real
    produto = _fonte().normalizar(item)
    assert produto.original_price is None


def test_titulo_ausente_usa_placeholder():
    item = {**ITEM_VALIDO}
    del item["productName"]
    produto = _fonte().normalizar(item)
    assert produto.title == "(sem título)"


def test_dados_incompletos_sem_item_id_levanta_value_error():
    item = {**ITEM_VALIDO}
    del item["itemId"]
    with pytest.raises(ValueError):
        _fonte().normalizar(item)
