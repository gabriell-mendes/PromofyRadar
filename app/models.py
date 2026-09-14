"""Modelos de dados do domínio.

Product é o objeto normalizado que qualquer collector deve produzir,
independente da fonte (Mercado Livre, Amazon, etc). Ele espelha exatamente
o que está documentado em docs/data-model.md, se um campo mudar aqui,
atualize o doc (e vice-versa).

ReviewItem não é modelo de domínio, é o que a tela de revisão manual
precisa: um Product mais o resultado da análise (score, motivo, preço de
referência pra comparação "de/por"). Tanto os dados fictícios
(app/mock_data.py) quanto o collector real (app/collector.py +
app/scoring.py) produzem ReviewItem, é o formato comum que alimenta a
dashboard.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Product:
    source: str          # de qual fonte veio, ex: "mercadolivre"
    source_id: str        # id do produto/anúncio na fonte
    title: str             # título do produto
    price: Decimal          # preço atual
    url: str                  # link direto para o produto
    store: str                 # nome da loja/vendedor
    collected_at: datetime      # quando foi coletado


@dataclass
class ReviewItem:
    product: Product
    score: int              # 0-100, versão simplificada do Deal Score
    reason: str              # explicação curta e legível do motivo do score
    original_price: Decimal   # preço de referência ("de"), comparado com product.price ("por")
