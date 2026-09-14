"""Dashboard de revisão manual.

Serve UMA única página: recebe uma consulta (parâmetro "q" na URL, com um
valor padrão), busca produtos reais na fonte de ofertas configurada
(app/config.py — hoje, Shopee por padrão, ver docs/decisao-fonte-de-dados.md),
calcula um Deal Score simplificado e mostra a lista pronta pra você decidir
o que publicar. É a interface para a etapa "revisão manual" do MVP
(docs/roadmap.md), ligada nas etapas anteriores do pipeline (consulta ->
fonte -> normalização -> análise/Deal Score).

Este módulo não sabe (e não deveria saber) qual fonte concreta está em
uso — só fala com a interface OfferSource via get_source(). Ver
docs/architecture.md.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_source
from .message import format_price, generate_message
from .models import ReviewItem
from .scoring import calcular_deal_score, gerar_motivo
from .sources.base import OfferSourceError

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Grupo de Ofertas — Revisão Manual")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

QUERY_PADRAO = "notebook"


def score_class(score: int) -> str:
    """Classe CSS pra colorir o score, regra simples, sem mágica."""
    if score >= 70:
        return "score-good"
    if score >= 50:
        return "score-mid"
    return "score-bad"


def montar_review_items(fonte, query: str) -> list[ReviewItem]:
    """Pipeline completo de hoje: busca (na fonte configurada) -> pontua.

    A normalização já acontece dentro da fonte (OfferSource.buscar_produtos),
    então aqui só sobra buscar e pontuar — cada etapa continua isolada e
    testável sozinha (fonte em app/sources/*, score em app/scoring.py), isso
    aqui só encadeia as chamadas.
    """
    produtos = fonte.buscar_produtos(query)
    precos = [p.price for p in produtos]

    itens = []
    for produto in produtos:
        score = calcular_deal_score(produto, precos)
        motivo = gerar_motivo(produto, precos)
        itens.append(ReviewItem(product=produto, score=score, reason=motivo))
    return itens


@app.get("/")
def review(request: Request, q: str = QUERY_PADRAO):
    erro = None
    review_items: list[ReviewItem] = []
    nome_fonte = "?"
    try:
        fonte = get_source()
        nome_fonte = fonte.name
        review_items = montar_review_items(fonte, q)
    except (OfferSourceError, ValueError) as exc:
        # Falha da fonte (rede/API/config, incluindo OFFER_SOURCE mal
        # configurado) não deveria derrubar a página inteira, só mostrar o
        # que aconteceu. Isso é robustez básica de quem chama uma fonte
        # externa, não overengineering.
        erro = f"Não deu pra buscar produtos agora: {exc}"

    items = [
        {
            "product": item.product,
            "score": item.score,
            "reason": item.reason,
            "score_class": score_class(item.score),
            "price_current": format_price(item.product.price),
            "price_original": format_price(item.product.original_price or item.product.price),
            "message": generate_message(item),
        }
        for item in review_items
    ]

    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "items": items,
            "query": q,
            "erro": erro,
            "fonte": nome_fonte,
        },
    )
