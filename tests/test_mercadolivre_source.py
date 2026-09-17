"""Mercado Livre está desativado por decisão de arquitetura (ver
docs/decisao-fonte-de-dados.md). O teste importante aqui não é "a API
funciona", é o oposto: garantir que usar essa fonte falha de forma clara
e imediata, SEM tentar uma requisição de rede contra um endpoint que
sabemos bloqueado — e que a lógica de normalização continua correta caso
a certificação de parceiro um dia libere o acesso.
"""

from unittest.mock import patch

import pytest

from app.sources.base import SourceUnavailableError
from app.sources.mercadolivre import MercadoLivreSource

ITEM_VALIDO = {
    "id": "MLB123",
    "title": "Notebook Exemplo",
    "price": 2500,
    "original_price": 2999,
    "permalink": "https://mercadolivre.com.br/produto-exemplo",
    "thumbnail": "https://img.exemplo.com/x.jpg",
    "seller": {"nickname": "Loja Exemplo"},
}


@patch("app.sources.mercadolivre.requests.get")
def test_fonte_desativada_nao_faz_chamada_de_rede(mock_get):
    with pytest.raises(SourceUnavailableError, match="PA_UNAUTHORIZED_RESULT_FROM_POLICIES"):
        MercadoLivreSource().buscar_produtos_raw("notebook")
    mock_get.assert_not_called()


def test_normalizacao_continua_correta_para_quando_o_bloqueio_acabar():
    fonte = MercadoLivreSource()
    produto = fonte.normalizar(ITEM_VALIDO)

    # "mercadolivre_api", não "mercadolivre": desde 2026-09-16 esse nome
    # ficou reservado pra fonte ativa (scraping, ver
    # app/sources/mercadolivre_scraper.py) — esta classe é a API oficial,
    # mantida só como referência (ver docstring do arquivo).
    assert produto.source == "mercadolivre_api"
    assert produto.source_id == "MLB123"
    assert str(produto.price) == "2500"
    assert str(produto.original_price) == "2999"
    assert produto.url == "https://mercadolivre.com.br/produto-exemplo"
    assert produto.store == "Loja Exemplo"


def test_produto_sem_preco_levanta_value_error():
    item = {**ITEM_VALIDO, "price": None}
    with pytest.raises(ValueError):
        MercadoLivreSource().normalizar(item)


def test_produto_sem_link_levanta_value_error():
    item = {**ITEM_VALIDO, "permalink": None}
    with pytest.raises(ValueError):
        MercadoLivreSource().normalizar(item)
