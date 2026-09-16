"""Filtro de desconto mínimo.

Etapa "filtro das melhores ofertas" do pipeline (ver docs/architecture.md):
decide se um Product já normalizado tem desconto real o suficiente pra
valer a pena mostrar na revisão manual.

Separado de app/scoring.py de propósito, porque são duas perguntas
diferentes sobre o mesmo produto:

- scoring.py (Deal Score) é RELATIVO: compara o preço do produto com a
  mediana dos preços da MESMA busca. Responde "esse produto está barato
  perto dos outros resultados?".
- filtro.py é ABSOLUTO: compara o preço do produto com o preço "de" que a
  própria fonte informou. Responde "esse produto específico está com
  desconto de verdade?".

Um produto pode ter Deal Score alto (mais barato que a mediana da busca)
sem ter desconto nenhum sobre o preço original dele — e vice-versa. As
duas continuam independentes por decisão, uma não substitui a outra.
"""

from __future__ import annotations

from .models import Product


def calcular_desconto_percentual(produto: Product) -> float | None:
    """Desconto real do produto, comparando price com original_price.

    Devolve None quando não dá pra calcular: a fonte não informou preço
    "de" (original_price é None), ou o normalizar() da fonte já descartou
    esse valor por não representar desconto real (original_price <= price
    — cada fonte já faz essa checagem antes de virar Product, ver
    app/sources/*.py).
    """
    if produto.original_price is None or produto.original_price <= 0:
        return None
    if produto.price is None:
        return None

    desconto = (produto.original_price - produto.price) / produto.original_price
    return float(desconto) * 100


def atende_desconto_minimo(produto: Product, minimo_percentual: float) -> bool:
    """True se o produto tem desconto igual ou maior que minimo_percentual.

    Produto sem desconto conhecido (fonte não informou preço "de") não
    atende, mesmo com minimo_percentual=0 — não dá pra provar desconto
    nenhum, então não faz sentido aparecer num filtro que existe
    justamente pra mostrar só quem tem desconto de verdade.
    """
    desconto = calcular_desconto_percentual(produto)
    return desconto is not None and desconto >= minimo_percentual
