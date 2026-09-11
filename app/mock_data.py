"""Dados fictícios para desenvolver e testar a dashboard de revisão
antes de existir um collector real.

ReviewItem NÃO é um modelo de domínio — é só o que a tela de revisão
precisa: um Product + o resultado (fictício, por enquanto) da etapa de
análise/Deal Score. Quando o Deal Score real existir, ele vai produzir
objetos assim (ou parecidos) para alimentar essa mesma tela.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .models import Product


@dataclass
class ReviewItem:
    product: Product
    score: int      # 0-100, versão simplificada do Deal Score (fictício aqui)
    reason: str       # explicação curta e legível do motivo do score


MOCK_REVIEW_ITEMS = [
    ReviewItem(
        product=Product(
            source="mercadolivre",
            source_id="MLB111",
            title="Notebook Acer Aspire 5 Ryzen 5 8GB 256GB SSD",
            price=Decimal("2399.00"),
            url="https://www.mercadolivre.com.br/exemplo-notebook-acer",
            store="Loja Oficial Acer",
            collected_at=datetime(2026, 9, 11, 9, 0),
        ),
        score=82,
        reason="12% abaixo do preço médio dos últimos 30 dias (dado fictício)",
    ),
    ReviewItem(
        product=Product(
            source="mercadolivre",
            source_id="MLB222",
            title="SSD NVMe Kingston NV2 1TB",
            price=Decimal("349.90"),
            url="https://www.mercadolivre.com.br/exemplo-ssd-kingston",
            store="Kingston Store",
            collected_at=datetime(2026, 9, 11, 9, 5),
        ),
        score=58,
        reason="Preço igual à média recente — desconto anunciado não é real (dado fictício)",
    ),
    ReviewItem(
        product=Product(
            source="mercadolivre",
            source_id="MLB333",
            title="Monitor Gamer LG UltraGear 27' 144Hz",
            price=Decimal("1199.00"),
            url="https://www.mercadolivre.com.br/exemplo-monitor-lg",
            store="LG Store Oficial",
            collected_at=datetime(2026, 9, 11, 9, 10),
        ),
        score=91,
        reason="Menor preço dos últimos 90 dias (dado fictício)",
    ),
    ReviewItem(
        product=Product(
            source="mercadolivre",
            source_id="MLB444",
            title="Placa de Vídeo AMD Radeon RX 6600 8GB",
            price=Decimal("1450.00"),
            url="https://www.mercadolivre.com.br/exemplo-rx6600",
            store="Vendedor não oficial",
            collected_at=datetime(2026, 9, 11, 9, 15),
        ),
        score=39,
        reason="Loja sem histórico de confiabilidade + preço acima da média (dado fictício)",
    ),
]
