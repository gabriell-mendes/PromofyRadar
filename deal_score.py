"""Deal Score: nota de 0 a 100 para uma oferta, por regras explicitas.

Funcao pura: recebe numeros e devolve um dict. Nao conhece Playwright,
banco nem painel, so preco, preco "de" anunciado, precos do grupo coletado
e precos historicos do proprio produto. Nenhuma IA decide aqui.

Escala: 0 = nao esta mais barato que o normal, 100 = pelo menos 30% abaixo
da referencia. O desconto anunciado pela loja NUNCA soma pontos. Ele so
serve para acusar desconto inflado (flag), quando ha historico para provar.

Fatores (cada um vira uma nota de 0 a 1):
- historico: desconto real contra a MEDIANA dos ultimos dias do proprio produto
- grupo:     desconto real contra a MEDIANA dos precos da mesma coleta
- minimo:    quao perto (ou abaixo) do menor preco recente esta

Sem historico suficiente, so o fator grupo vale e a confianca fica "baixa".
Sem historico e sem grupo suficiente, nao ha como julgar: score None.
Pesos dos fatores disponiveis sao renormalizados para somar 100.
"""

from __future__ import annotations

import statistics

PESOS = {"historico": 50, "grupo": 30, "minimo": 20}

TETO_DESCONTO = 0.30        # 30% abaixo da referencia ja e nota maxima
TOLERANCIA_MINIMO = 0.15    # 15% acima do menor preco recente zera o fator "minimo"
MIN_GRUPO = 5               # menos que isso, a mediana da coleta nao significa nada
MIN_DIAS_HISTORICO = 3      # dias distintos com preco registrado para confiar no historico
LIMITE_INFLADO = 0.20       # "de" anunciado 20% acima do preco que o produto costuma ter
DESCONTO_MIN_PARA_INFLADO = 10.0  # so acusa se a loja anuncia pelo menos isso (%)

FAIXAS = [(75, "Ótima"), (50, "Boa"), (25, "Regular"), (0, "Fraca")]


def _clamp(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


def calcular_desconto_real(preco_atual: float, preco_referencia: float) -> float:
    """(referencia - atual) / referencia. Negativo se o preco esta acima."""
    if preco_referencia <= 0:
        return 0.0
    return (preco_referencia - preco_atual) / preco_referencia


def nota_desconto(desconto_real: float) -> float:
    """Desconto real vira nota 0..1, com teto em TETO_DESCONTO."""
    return _clamp(desconto_real / TETO_DESCONTO)


def nota_minimo(preco_atual: float, menor_recente: float) -> float:
    """1.0 se esta no menor preco recente (ou abaixo), cai ate 0 a TOLERANCIA_MINIMO acima."""
    if menor_recente <= 0 or preco_atual <= menor_recente:
        return 1.0
    acima = (preco_atual - menor_recente) / menor_recente
    return _clamp(1 - acima / TOLERANCIA_MINIMO)


def faixa(score: int | None) -> str:
    if score is None:
        return "Sem nota"
    for minimo, nome in FAIXAS:
        if score >= minimo:
            return nome
    return "Fraca"


def _pct(valor: float) -> int:
    return round(valor * 100)


def avaliar(
    preco: float,
    preco_anunciado: float | None,
    precos_grupo: list[float],
    historico: list[float],
) -> dict:
    """Devolve {score, confianca, motivos, flags, detalhe}.

    preco_anunciado: o "de" da loja (so para a flag de desconto inflado).
    precos_grupo:    precos validos de TODOS os itens vistos na mesma coleta.
    historico:       precos de dias anteriores do mesmo produto (um por dia).
    """
    resultado = {"score": None, "confianca": "nenhuma", "motivos": [], "flags": [], "detalhe": {}}

    # Gate: preco invalido nao recebe nota neutra, recebe nenhuma nota.
    if preco is None or preco <= 0:
        resultado["flags"].append("preco_invalido")
        resultado["motivos"].append("Preço inválido, não deve ser publicado")
        return resultado

    grupo = [p for p in precos_grupo if p and p > 0]
    hist = [p for p in historico if p and p > 0]
    tem_hist = len(hist) >= MIN_DIAS_HISTORICO
    tem_grupo = len(grupo) >= MIN_GRUPO

    fatores = {}  # nome -> nota 0..1
    detalhe = resultado["detalhe"]

    if tem_hist:
        ref_hist = statistics.median(hist)
        menor = min(hist)
        d_hist = calcular_desconto_real(preco, ref_hist)
        fatores["historico"] = nota_desconto(d_hist)
        # "minimo" so vale na proporcao do desconto real: produto de preco estavel vive
        # perto do proprio minimo e nao pode ganhar pontos por isso (nem por ruido de centavos).
        fatores["minimo"] = nota_minimo(preco, menor) * fatores["historico"]
        detalhe.update(ref_historico=round(ref_hist, 2), menor_recente=round(menor, 2), dias_historico=len(hist))
        lado = "abaixo" if d_hist >= 0 else "acima"
        resultado["motivos"].append(f"{abs(_pct(d_hist))}% {lado} da mediana dos últimos {len(hist)} dias")
        if preco < menor:
            resultado["flags"].append("menor_preco_recente")
            resultado["motivos"].append(f"Menor preço registrado (antes: R$ {menor:.2f})")

        # Desconto inflado: a loja diz "de X" mas o produto nunca custou perto de X.
        if preco_anunciado and preco_anunciado > preco:
            anunciado_pct = (preco_anunciado - preco) / preco_anunciado * 100
            if (
                anunciado_pct >= DESCONTO_MIN_PARA_INFLADO
                and (preco_anunciado - ref_hist) / ref_hist > LIMITE_INFLADO
            ):
                resultado["flags"].append("desconto_inflado")
                resultado["motivos"].append(
                    f"Desconto anunciado ({anunciado_pct:.0f}%) não confere: o preço normal era R$ {ref_hist:.2f}"
                )

    if tem_grupo:
        ref_grupo = statistics.median(grupo)
        d_grupo = calcular_desconto_real(preco, ref_grupo)
        fatores["grupo"] = nota_desconto(d_grupo)
        detalhe.update(ref_grupo=round(ref_grupo, 2), tamanho_grupo=len(grupo))
        lado = "abaixo" if d_grupo >= 0 else "acima"
        resultado["motivos"].append(f"{abs(_pct(d_grupo))}% {lado} da mediana desta coleta ({len(grupo)} itens)")

    if not fatores:
        resultado["motivos"].append("Poucos dados: sem histórico do produto e sem itens suficientes para comparar")
        return resultado

    soma_pesos = sum(PESOS[n] for n in fatores)
    score = sum(fatores[n] * PESOS[n] for n in fatores) / soma_pesos * 100
    resultado["score"] = int(_clamp(round(score), 0, 100))
    resultado["confianca"] = "alta" if tem_hist else "baixa"
    if not tem_hist:
        resultado["motivos"].append("Sem histórico do produto ainda: nota baseada só na comparação com esta coleta")
    return resultado
