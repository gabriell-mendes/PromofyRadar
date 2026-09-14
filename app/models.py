"""Modelos de dados do domínio.

Product é o objeto normalizado que qualquer fonte (app/sources/*) deve
produzir, independente de onde os dados vieram (Shopee, Mercado Livre,
etc). Ele espelha exatamente o que está documentado em docs/data-model.md,
se um campo mudar aqui, atualize o doc (e vice-versa).

Os três campos opcionais (original_price, image_url, sales) existem porque
pelo menos uma fonte real hoje (Shopee) os fornece e eles alimentam
diretamente a mensagem de publicação e o Deal Score. Nenhum campo foi
adicionado "por completude" — só o que já é usado em algum lugar do
pipeline (ver docs/data-model.md, seção "Fora do MVP" pra campos que
foram cogitados e descartados por enquanto).

ReviewItem não é modelo de domínio, é o que a tela de revisão manual
precisa: um Product mais o resultado da análise (score, motivo). O preço
"de" pra comparação "de/por" não é campo próprio do ReviewItem — vem de
`product.original_price`, com fallback pro próprio `product.price` quando a
fonte não informou preço anterior (ver app/message.py e app/main.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Product:
    source: str                          # de qual fonte veio, ex: "shopee", "mercadolivre"
    source_id: str                       # id do produto/anúncio na fonte
    title: str                           # título do produto
    price: Decimal                       # preço atual
    url: str                             # link direto para o produto
    store: str                           # nome da loja/vendedor
    collected_at: datetime               # quando foi coletado
    original_price: Decimal | None = None  # preço "de" anunciado pela fonte/loja, quando existe
    image_url: str | None = None         # imagem do produto, quando a fonte fornece
    sales: int | None = None             # volume de vendas reportado pela fonte, quando existe


@dataclass
class ReviewItem:
    product: Product
    score: int    # 0-100, versão simplificada do Deal Score
    reason: str   # explicação curta e legível do motivo do score
