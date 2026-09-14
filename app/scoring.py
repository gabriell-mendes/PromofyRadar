"""Análise / Deal Score.

Só conhece Product já normalizado, não sabe de onde ele veio (Mercado
Livre, Amazon etc). Nenhuma IA decide se a oferta é boa aqui, é uma regra
matemática explícita sobre os dados coletados, como pedem os princípios do
projeto.

Limitação conhecida, registrada de propósito (não escondida): ainda não
existe histórico de preços (isso é "depois do MVP" em docs/roadmap.md).
Então o único dado real disponível hoje pra comparar é: os OUTROS preços
retornados na MESMA busca. O score aqui é relativo a esse grupo, não a um
preço "justo" absoluto. Se toda a busca vier com preços inflados, nada vai
ganhar nota alta por isso sozinho, isso só melhora quando existir
histórico de preços de verdade.
"""

import statistics
from decimal import Decimal

from .models import Product


def calcular_deal_score(produto: Product, precos_da_busca: list[Decimal]) -> int:
    """Score de 0 a 100. Regra: quanto mais abaixo da MEDIANA dos preços
    encontrados nesta busca, maior o score. Mediana (e não média) porque um
    único anúncio absurdamente caro ou barato não distorce tanto o
    resultado.
    """
    if len(precos_da_busca) < 2:
        return 50  # não há com o que comparar, nota neutra

    mediana = statistics.median(precos_da_busca)
    if mediana == 0:
        return 50

    diferenca = (mediana - produto.price) / mediana  # positivo = mais barato que a mediana
    score = 50 + float(diferenca) * 200
    return max(0, min(100, round(score)))


def gerar_motivo(produto: Product, precos_da_busca: list[Decimal]) -> str:
    """Explicação curta e legível do score, pra quem está revisando
    entender de onde veio a nota sem ter que ler o código.
    """
    if len(precos_da_busca) < 2:
        return "Só um resultado nesta busca, sem grupo pra comparar"

    mediana = statistics.median(precos_da_busca)
    if mediana == 0:
        return "Preço mediano da busca é zero, não deu pra comparar"

    diferenca_pct = round(float((mediana - produto.price) / mediana) * 100)
    n = len(precos_da_busca)
    if diferenca_pct > 0:
        return f"{diferenca_pct}% abaixo da mediana desta busca ({n} resultados)"
    if diferenca_pct < 0:
        return f"{abs(diferenca_pct)}% acima da mediana desta busca ({n} resultados)"
    return f"Preço igual à mediana desta busca ({n} resultados)"
