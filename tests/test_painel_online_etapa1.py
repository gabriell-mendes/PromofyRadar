import pytest
from pydantic import ValidationError

from painel_online.schemas import OfertaIn
from painel_online.upsert import chave_da_oferta, decidir

LINK_A = "https://www.mercadolivre.com.br/produto-x/p/MLB25171538?pdp_filters=category%3AMLB1648"
LINK_B = "https://www.mercadolivre.com.br/produto-x/p/MLB25171538?searchVariation=123&tracking_id=abc"


def _oferta(url=LINK_A, preco=100.0):
    return OfertaIn(loja="mercadolivre", url=url, titulo="Produto X", preco=preco)


def test_defaults_dos_opcionais():
    o = _oferta()
    assert o.preco_original is None
    assert o.deal_motivos == [] and o.deal_flags == []
    assert o.deal_motivos is not o.deal_flags


@pytest.mark.parametrize("preco", [0, -5])
def test_preco_precisa_ser_positivo(preco):
    with pytest.raises(ValidationError):
        _oferta(preco=preco)


def test_campos_obrigatorios():
    with pytest.raises(ValidationError):
        OfertaIn(loja="mercadolivre", url=LINK_A, preco=10)


def test_id_produto_derivado_da_url():
    assert chave_da_oferta(_oferta()) == ("mercadolivre", "MLB25171538")


def test_mesmo_produto_com_query_diferente_vira_atualizacao():
    existentes: set = set()
    assert decidir(_oferta(LINK_A), existentes) == "novo"
    existentes.add(chave_da_oferta(_oferta(LINK_A)))
    assert decidir(_oferta(LINK_B, preco=90.0), existentes) == "atualizacao"


def test_loja_diferente_e_produto_diferente():
    existentes = {("mercadolivre", "MLB25171538")}
    outra = OfertaIn(loja="outraloja", url=LINK_A, titulo="X", preco=10)
    assert decidir(outra, existentes) == "novo"
