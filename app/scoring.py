"""Análise / Deal Score.

Só conhece Product já normalizado, não sabe de onde ele veio (Shopee,
Mercado Livre etc). Nenhuma IA decide se a oferta é boa aqui, é uma regra
matemática explícita sobre os dados coletados, como pedem os princípios do
projeto.

Limitação conhecida, registrada de propósito (não escondida): ainda não
existe histórico de preços (isso é "depois do MVP" em docs/roadmap.md).
Então o dado real disponível hoje pra comparar é: os OUTROS preços
retornados na MESMA busca, mais — quando a fonte fornece (hoje, só a
Shopee) — o volume de vendas do produto (`Product.sales`), usado só como
um pequeno ajuste de confiança, não como fator principal: um produto sem
nenhuma venda registrada não é necessariamente ruim, mas também não tem
prova nenhuma de que a oferta é real, o que pesa um pouco contra ele.
"""

import statistics
from decimal import Decimal

from .models import Product

SEM_VENDAS_PENALIDADE = 10


def calcular_deal_score(produto: Product, precos_da_busca: list[Decimal]) -> int:
    """Score de 0 a 100. Regra: quanto mais abaixo da MEDIANA dos preços
    encontrados nesta busca, maior o score. Mediana (e não média) porque um
    único anúncio absurdamente caro ou barato não distorce tanto o
    resultado.
    """
    if produto.price is None or produto.price <= 0:
        return 0  # preço inválido não é "nota neutra", é motivo de descartar a oferta

    if len(precos_da_busca) < 2:
        score = 50  # não há com o que comparar, nota neutra
    else:
        mediana = statistics.median(precos_da_busca)
        if mediana == 0:
            score = 50
        else:
            diferenca = (mediana - produto.price) / mediana  # positivo = mais barato que a mediana
            score = 50 + float(diferenca) * 200

    if produto.sales == 0:
        score -= SEM_VENDAS_PENALIDADE

    return max(0, min(100, round(score)))


def gerar_motivo(produto: Product, precos_da_busca: list[Decimal]) -> str:
    """Explicação curta e legível do score, pra quem está revisando
    entender de onde veio a nota sem ter que ler o código.
    """
    if produto.price is None or produto.price <= 0:
        return "Preço inválido coletado — não deveria ser publicado"

    if len(precos_da_busca) < 2:
        base = "Só um resultado nesta busca, sem grupo pra comparar"
    else:
        mediana = statistics.median(precos_da_busca)
        if mediana == 0:
            base = "Preço mediano da busca é zero, não deu pra comparar"
        else:
            diferenca_pct = round(float((mediana - produto.price) / mediana) * 100)
            n = len(precos_da_busca)
            if diferenca_pct > 0:
                base = f"{diferenca_pct}% abaixo da mediana desta busca ({n} resultados)"
            elif diferenca_pct < 0:
                base = f"{abs(diferenca_pct)}% acima da mediana desta busca ({n} resultados)"
            else:
                base = f"Preço igual à mediana desta busca ({n} resultados)"

    if produto.sales == 0:
        base += " — sem vendas registradas ainda"

    return base
