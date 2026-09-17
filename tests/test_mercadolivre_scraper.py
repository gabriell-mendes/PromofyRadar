"""Testes de app/sources/mercadolivre_scraper.py: extração a partir de
HTML já baixado (sem navegador nem rede) e a correção de 2026-09-17
(source_id/url vindo de um link de tracking, não do produto direto).

_extrair_itens_crus() e normalizar() não dependem do Playwright, só de
uma string de HTML — por isso dá pra testar com um HTML fixo, sem
navegador real (o download em si, _baixar_html_busca(), é a única parte
que precisa de um navegador de verdade, e fica fora destes testes de
propósito).
"""

from decimal import Decimal

import pytest

from app.sources.mercadolivre_scraper import (
    MercadoLivreScraperSource,
    _extrair_itens_crus,
    _item_id_da_url,
)

# URL de tracking real, capturada de uma busca de verdade (ver conversa do
# projeto), usada aqui pra garantir que a extração do ID sobrevive ao
# formato real do link — não a uma versão simplificada inventada só pro
# teste passar.
URL_TRACKING_REAL = (
    "https://click1.mercadolivre.com.br/mclics/clicks/external/MLB/count"
    "?a=abc123&searchVariation=198296097451"
    "&pdp_filters=item_id%3AMLB6448442404"
    "#polycard_client=search-desktop&tracking_id=xyz"
)

HTML_BUSCA_EXEMPLO = f"""
<ul>
  <li class="ui-search-layout__item">
    <a class="poly-component__title" href="{URL_TRACKING_REAL}">Camiseta Preta Basica</a>
    <span class="poly-component__seller">Loja Exemplo</span>
    <span class="andes-money-amount">
      <span class="andes-money-amount__fraction">59</span>
      <span class="andes-money-amount__cents">90</span>
    </span>
    <s class="andes-money-amount--previous">
      <span class="andes-money-amount">
        <span class="andes-money-amount__fraction">99</span>
        <span class="andes-money-amount__cents">90</span>
      </span>
    </s>
  </li>
  <li class="ui-search-layout__item">
    <!-- card sem título reconhecível (ex: propaganda misturada na
    listagem) -- _extrair_itens_crus deve pular, não quebrar a busca -->
    <span class="poly-component__seller">Propaganda</span>
  </li>
</ul>
"""


def test_item_id_da_url_extrai_o_id_de_dentro_do_link_de_tracking():
    assert _item_id_da_url(URL_TRACKING_REAL) == "MLB6448442404"


def test_item_id_da_url_sem_pdp_filters_cai_no_fallback_generico():
    # Uma URL "normal" (sem tracking), caso o Mercado Livre volte a usar
    # isso no futuro -- continua funcionando via _item_id() genérico.
    url_direta = "https://produto.mercadolivre.com.br/MLB-999888777"
    assert _item_id_da_url(url_direta) == "MLB999888777"


def test_item_id_da_url_sem_id_nenhum_devolve_none():
    assert _item_id_da_url("https://mercadolivre.com.br/sem-id-aqui") is None


def test_extrair_itens_crus_ignora_card_sem_titulo():
    itens = _extrair_itens_crus(HTML_BUSCA_EXEMPLO)
    assert len(itens) == 1


def test_extrair_itens_crus_le_preco_atual_e_anterior_corretamente():
    item = _extrair_itens_crus(HTML_BUSCA_EXEMPLO)[0]
    assert str(item["current_price"]) == "59.90"
    assert str(item["previous_price"]) == "99.90"


def test_normalizar_usa_id_estavel_e_link_direto_em_vez_do_de_tracking():
    item_cru = _extrair_itens_crus(HTML_BUSCA_EXEMPLO)[0]
    produto = MercadoLivreScraperSource().normalizar(item_cru)

    assert produto.source_id == "MLB6448442404"
    assert produto.url == "https://produto.mercadolivre.com.br/MLB6448442404"
    assert str(produto.price) == "59.90"
    assert str(produto.original_price) == "99.90"


def test_normalizar_sem_id_extraivel_levanta_value_error():
    # Preço presente (senão levantaria por outro motivo antes de chegar
    # na checagem do ID) mas URL sem nenhum MLB extraível -- isola o caso
    # que queremos testar aqui.
    item_cru = {
        "title": "Produto sem ID",
        "url": "https://mercadolivre.com.br/sem-id-aqui",
        "current_price": Decimal("59.90"),
        "previous_price": None,
        "seller": "Loja",
    }
    with pytest.raises(ValueError, match="ID do produto"):
        MercadoLivreScraperSource().normalizar(item_cru)
