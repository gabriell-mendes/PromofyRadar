"""Geração da mensagem de publicação.

Mantido separado do resto (collector, análise) porque é uma etapa com uma
única responsabilidade: pegar um item já analisado e montar o texto pronto
para publicação manual (copiar e colar no Telegram, por enquanto).
"""

from .mock_data import ReviewItem


def format_price(price) -> str:
    return f"R$ {price:.2f}".replace(".", ",")


def generate_message(item: ReviewItem) -> str:
    p = item.product
    return (
        f"🔥 {p.title}\n\n"
        f"💰 {format_price(p.price)}\n"
        f"🏪 {p.store}\n"
        f"⭐ Deal Score: {item.score}/100\n"
        f"{item.reason}\n\n"
        f"👉 {p.url}"
    )
