"""Geração da mensagem de publicação.

Mantido separado do resto (fontes, análise) porque é uma etapa com uma
única responsabilidade: pegar um item já analisado e montar o texto pronto
para publicação manual (copiar e colar no Telegram, por enquanto).

O Deal Score (item.score) é informação de trabalho interno — só aparece na
dashboard, pra quem está revisando decidir se publica. Ele NÃO entra na
mensagem: quem recebe a oferta no canal não precisa (nem deveria precisar)
ver uma nota interna pra confiar na oferta — o preço "de/por" já fala por
si.

O link de afiliado NÃO é gerado aqui (decisão registrada em
docs/decisao-fonte-de-dados.md): a mensagem sempre usa o link normal do
produto (`product.url`); o Gabriel gera o link de afiliado manualmente,
depois de revisar, fora do código.
"""

from .models import ReviewItem


def format_price(price) -> str:
    return f"R$ {price:.2f}".replace(".", ",")


def generate_message(item: ReviewItem) -> str:
    p = item.product
    preco_de = p.original_price or p.price
    return (
        f"🔥 {p.title}\n\n"
        f"💰 De {format_price(preco_de)} por {format_price(p.price)}\n"
        f"🏪 {p.store}\n"
        f"{item.reason}\n\n"
        f"👉 {p.url}"
    )
