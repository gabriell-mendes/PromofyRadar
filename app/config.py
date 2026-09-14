"""Configuração e seleção de fonte de ofertas.

Único lugar do projeto que sabe "qual fonte concreta existe pra cada
nome" — app/main.py só chama get_source() e trabalha com a interface
OfferSource (app/sources/base.py) depois disso. Trocar a fonte padrão, ou
adicionar uma nova, não deve exigir tocar em main.py/scoring.py/message.py
(ver docs/architecture.md).
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv é opcional: em produção as variáveis podem vir do
    # ambiente diretamente (ex: variáveis de sistema, container, CI).
    pass

from .sources.base import OfferSource
from .sources.mercadolivre import MercadoLivreSource
from .sources.shopee import ShopeeSource

FONTES: dict[str, type[OfferSource]] = {
    "shopee": ShopeeSource,
    "mercadolivre": MercadoLivreSource,
}

FONTE_PADRAO = "shopee"


def get_source(nome: str | None = None) -> OfferSource:
    """Instancia a fonte pelo nome (ou pela variável de ambiente
    OFFER_SOURCE, ou pela fonte padrão do MVP — ver FONTE_PADRAO acima).
    """
    nome = nome or os.environ.get("OFFER_SOURCE", FONTE_PADRAO)
    try:
        classe = FONTES[nome]
    except KeyError:
        disponiveis = ", ".join(sorted(FONTES))
        raise ValueError(
            f"Fonte de ofertas desconhecida: {nome!r}. Disponíveis: {disponiveis}"
        ) from None
    return classe()
