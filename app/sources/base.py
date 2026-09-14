"""Interface comum a qualquer fonte de ofertas.

Esta é a peça central da decisão arquitetural registrada em
docs/decisao-fonte-de-dados.md: nenhuma parte do projeto fora de
app/sources/<fonte>.py deve saber qual fonte está em uso, nem como o dado
cru dela é formatado. app/main.py, app/scoring.py e app/message.py
trabalham só com `Product` (app/models.py).

Cada fonte concreta:
- conhece o formato/protocolo da própria API (REST, GraphQL, o que for);
- sabe autenticar-se, paginar e respeitar rate limit dela;
- sabe transformar um item cru em `Product`;
- não sabe nada sobre Deal Score, dashboard ou outras fontes.

`buscar_produtos()` (implementado aqui, não em cada fonte) faz o trabalho
comum a todas: chama a fonte, normaliza cada item, pula (com log) itens
inválidos ou duplicados em vez de derrubar a busca inteira por causa de UM
item ruim. Isso cobre os casos de teste pedidos para "collector": resposta
com produto sem preço, produto duplicado ou dados incompletos não devem
quebrar os demais resultados.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..models import Product

logger = logging.getLogger(__name__)


class OfferSourceError(Exception):
    """Erro ao buscar ofertas numa fonte — envelope comum pra qualquer causa
    (rede, timeout, HTTP, autenticação, rate limit, resposta inesperada).

    app/main.py só precisa conhecer esta exceção, nunca a biblioteca HTTP ou
    o formato de erro específico de cada fonte — isso é o que permite trocar
    de fonte sem tocar no restante do sistema (ver docs/architecture.md).
    """


class SourceUnavailableError(OfferSourceError):
    """A fonte existe no código mas está deliberadamente desativada (ex:
    Mercado Livre — ver docs/decisao-fonte-de-dados.md). Diferente de
    OfferSourceError genérico porque o motivo aqui não é uma falha
    passageira (rede, timeout): é uma decisão registrada, então quem
    chamar pode decidir não tentar de novo nem fazer retry/backoff.
    """


class OfferSource(ABC):
    """Classe-base pra qualquer fonte de ofertas (Shopee, Mercado Livre, ...)."""

    #: identificador curto e estável da fonte, usado em Product.source,
    #: logs e no seletor de fonte (app/config.py). Ex: "shopee".
    name: str

    @abstractmethod
    def buscar_produtos_raw(self, query: str, limit: int = 20) -> list[dict]:
        """Busca produtos na fonte e devolve os itens NO FORMATO DA FONTE,
        sem transformar nada. Deve levantar OfferSourceError (ou subclasse)
        em caso de falha de rede, HTTP ou autenticação — nunca deixar
        vazar a exceção nativa da biblioteca HTTP usada internamente.
        """

    @abstractmethod
    def normalizar(self, item_cru: dict) -> Product:
        """Converte UM item cru da fonte num Product padronizado.

        Deve levantar ValueError quando o item não tem dados suficientes
        pra virar uma oferta publicável (por exemplo, sem preço válido ou
        sem link) — buscar_produtos() abaixo trata isso pulando o item, não
        interrompendo a busca inteira.
        """

    def buscar_produtos(self, query: str, limit: int = 20) -> list[Product]:
        """Busca e normaliza numa chamada só, tolerando itens ruins.

        Comportamento comum a qualquer fonte:
        - item sem preço válido / dados incompletos → pulado, com log;
        - item duplicado (mesmo source_id) → só o primeiro é mantido;
        - erro de rede/HTTP → propaga como OfferSourceError (quem chama
          decide o que fazer, ex: mostrar erro na dashboard sem derrubar a
          página, como já faz app/main.py).
        """
        crus = self.buscar_produtos_raw(query, limit)

        produtos: list[Product] = []
        ids_vistos: set[str] = set()
        for item_cru in crus:
            try:
                produto = self.normalizar(item_cru)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "Item descartado na normalização (fonte=%s, query=%r): %s",
                    self.name, query, exc,
                )
                continue

            if produto.source_id in ids_vistos:
                logger.warning(
                    "Item duplicado descartado (fonte=%s, source_id=%s)",
                    self.name, produto.source_id,
                )
                continue

            ids_vistos.add(produto.source_id)
            produtos.append(produto)

        return produtos
