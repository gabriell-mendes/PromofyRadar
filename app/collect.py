"""CLI de coleta manual de ofertas (etapa "coleta" do pipeline).

Único módulo do projeto, além dos testes, que dispara uma busca de
verdade contra a fonte configurada (ver app/config.py). A dashboard
(app/main.py) continua fazendo busca ao vivo por enquanto, sem ler daqui
— separar essas duas responsabilidades de vez (dashboard só leitura,
coleta só aqui) é a mudança maior registrada em
"Claude outputs/contexto-para-retomar.md", ainda não aplicada nesta
etapa. O que foi resolvido agora foi só a coleta com histórico em si:
não repetir a mesma oferta, atualizar quando o preço/desconto mudar.

De propósito, uma query por execução (rodar várias buscas encadeadas numa
chamada só foi descartado, ver conversa) — pra rodar mais de uma busca,
chama o comando de novo.

Fluxo de uma execução:
  busca (fonte) -> calcula desconto (filtro.py) -> só quem atinge o
  mínimo segue -> compara com o que já estava salvo (storage.py) -> se
  for novo, ou o preço/desconto mudou desde a última vez, imprime como
  [NOVO] -> pontua (scoring.py) e salva/atualiza o registro de qualquer
  forma (pra a comparação da PRÓXIMA execução continuar funcionando).

Limitação conhecida, aceita de propósito por simplicidade (ver conversa
sobre o desenho): uma oferta que caiu ABAIXO do desconto mínimo não tem
seu registro atualizado enquanto ficar abaixo (só quem atinge o mínimo é
salvo, igual ao main.py já fazia antes de existir persistência). Na
prática isso só causa um falso negativo raro: se ela voltar a subir e
bater EXATAMENTE no mesmo preço e desconto de antes da queda, não seria
reportada de nova (pro banco, nada mudou). Qualquer variação de centavos
já resolve isso sozinho. Guardar histórico de quem nunca atingiu o mínimo
é possível depois, mas não é necessário agora (ver docs/roadmap.md).
"""

from __future__ import annotations

import argparse
import sys

from . import storage
from .config import DESCONTO_MINIMO_PADRAO, get_source
from .filtro import atende_desconto_minimo, calcular_desconto_percentual
from .models import Product
from .scoring import calcular_deal_score, gerar_motivo
from .sources.base import OfferSourceError


def _arredondar(valor: float | None) -> float | None:
    """Arredonda pra 2 casas antes de comparar dois descontos calculados
    em execuções diferentes — margem de segurança contra ruído de ponto
    flutuante, não porque já tenha acontecido, mas porque é barato
    garantir (ver app/filtro.py, calcular_desconto_percentual usa
    float(...) internamente).
    """
    return None if valor is None else round(valor, 2)


def _deveria_reportar(produto: Product, desconto_min: float, existente: dict | None) -> bool:
    """True quando essa oferta merece aparecer pra você agora.

    Regras (ver limitação conhecida na docstring do módulo):
    - não atinge o desconto mínimo -> nunca reporta, mesmo que já tenha
      sido reportada antes com um desconto maior (ela "sumiu" da lista,
      não é um erro, é o filtro fazendo o trabalho dele);
    - atinge o mínimo e nunca foi vista (ou nunca tinha atingido antes)
      -> reporta, é nova pra você;
    - atinge o mínimo e já existia salva com o MESMO preço e desconto ->
      não reporta de novo, você já viu essa oferta exata;
    - atinge o mínimo e existia com preço/desconto DIFERENTE -> reporta
      de novo (melhorou, ou voltou a atingir depois de ter caído).
    """
    if not atende_desconto_minimo(produto, desconto_min):
        return False
    if existente is None:
        return True

    desconto_novo = _arredondar(calcular_desconto_percentual(produto))
    desconto_salvo = _arredondar(existente.get("desconto_percentual"))
    return existente.get("price") != produto.price or desconto_salvo != desconto_novo


def coletar(query: str, desconto_min: float = DESCONTO_MINIMO_PADRAO) -> int:
    """Roda uma busca completa. Devolve o exit code do processo (0 =
    sucesso, mesmo que zero ofertas tenham sido encontradas ou salvas; 1 =
    falha ao buscar ou configuração inválida).
    """
    storage.inicializar_banco()

    try:
        fonte = get_source()
    except ValueError as exc:
        print(f"Configuração inválida: {exc}", file=sys.stderr)
        return 1

    try:
        produtos = fonte.buscar_produtos(query)
    except OfferSourceError as exc:
        print(f"Falha ao buscar {query!r} em {fonte.name!r}: {exc}", file=sys.stderr)
        return 1

    # Mesma decisão de app/main.py: a mediana do Deal Score usa TODOS os
    # produtos que a busca trouxe, antes do filtro de desconto (ver
    # docstring de montar_review_items em app/main.py pro motivo).
    precos = [p.price for p in produtos]
    salvas = 0
    reportadas = 0

    for produto in produtos:
        if not atende_desconto_minimo(produto, desconto_min):
            continue

        existente = storage.obter_oferta(produto.source, produto.source_id)
        reportar = _deveria_reportar(produto, desconto_min, existente)

        desconto = calcular_desconto_percentual(produto)
        score = calcular_deal_score(produto, precos)
        motivo = gerar_motivo(produto, precos)
        storage.salvar_oferta(produto, score, motivo, desconto)
        salvas += 1

        if reportar:
            reportadas += 1
            desconto_txt = f"{desconto:.0f}%" if desconto is not None else "?"
            print(f"[NOVO] {produto.title} | desconto {desconto_txt} | R$ {produto.price} | {produto.url}")

    print(
        f"\nBusca {query!r}: {len(produtos)} produto(s) encontrados, "
        f"{salvas} com desconto >= {desconto_min:.0f}%, "
        f"{reportadas} novo(s)/atualizado(s) pra revisar."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Coleta manual de ofertas (uma busca por execução), com histórico: "
        "não repete a mesma oferta duas vezes."
    )
    parser.add_argument("query")
    parser.add_argument(
        "--desconto-min",
        type=float,
        default=DESCONTO_MINIMO_PADRAO,
        dest="desconto_min",
        metavar="PERCENTUAL",
    )
    args = parser.parse_args()
    return coletar(args.query, args.desconto_min)


if __name__ == "__main__":
    raise SystemExit(main())
