"""Geração da mensagem de publicação.

Mantido separado do resto (collector, análise) porque é uma etapa com uma
única responsabilidade: pegar um item já analisado e montar o texto pronto
para publicação manual (copiar e colar no Telegram, por enquanto).

O Deal Score (item.score) é informação de trabalho interno — só aparece na
dashboard, pra quem está revisando decidir se publica. Ele NÃO entra na
mensagem: quem recebe a oferta no canal não precisa (nem deveria precisar)
ver uma nota interna pra confiar na oferta — o preço "de/por" já fala por si.
"""

from .mock_data import ReviewItem


def format_price(price) -> str:
    return f"R$ {price:.2f}".replace(".", ",")


def generate_message(item: ReviewItem) -> str:
    p = item.product
    return (
        f"🔥 {p.title}\n\n"
        f"💰 De {format_price(item.original_price)} por {format_price(p.price)}\n"
        f"🏪 {p.store}\n"
        f"{item.reason}\n\n"
        f"👉 {p.url}"
    )
