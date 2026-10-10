from collections.abc import Set

from historico import chave_produto

from .schemas import OfertaIn

Chave = tuple[str, str]


def chave_da_oferta(oferta: OfertaIn) -> Chave:
    """Identidade do produto no painel: (loja, id_produto)."""
    return (oferta.loja, chave_produto(oferta.url))


def decidir(oferta: OfertaIn, chaves_existentes: Set[Chave]) -> str:
    """Devolve "atualizacao" se a chave ja existe, senao "novo".

    Nao mexe em banco: quem chama fornece as chaves ja conhecidas e,
    depois da decisao, registra a nova chave.
    """
    if chave_da_oferta(oferta) in chaves_existentes:
        return "atualizacao"
    return "novo"
