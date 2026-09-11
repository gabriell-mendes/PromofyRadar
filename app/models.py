"""Modelos de dados do domínio.

Product é o objeto normalizado que qualquer collector deve produzir,
independente da fonte (Mercado Livre, Amazon, etc). Ele espelha exatamente
o que está documentado em docs/data-model.md — se um campo mudar aqui,
atualize o doc (e vice-versa).

Por enquanto isso não é usado por nenhum collector real (ainda não existe
nenhum). Ele existe primeiro para a dashboard de revisão poder trabalhar
com dados no formato certo desde já, usando dados fictícios
(app/mock_data.py) no lugar da coleta real.
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
