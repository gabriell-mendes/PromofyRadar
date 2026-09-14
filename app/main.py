"""Dashboard de revisão manual.

Serve UMA única página: recebe uma consulta (parâmetro "q" na URL, com um
valor padrão), busca produtos reais na API do Mercado Livre, calcula um
Deal Score simplificado e mostra a lista pronta pra você decidir o que
publicar. É a interface para a etapa "revisão manual" do MVP
(docs/roadmap.md), agora ligada nas etapas anteriores do pipeline
(consulta -> collector -> normalização -> análise/Deal Score).
"""

from pathlib import Path

import requests

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .collector import buscar_produtos_raw, extrair_preco_original, normalizar
from .message import format_price, generate_message
from .models import ReviewItem
from .scoring import calcular_deal_score, gerar_motivo

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


def montar_review_items(query: str) -> list[ReviewItem]:
    """Pipeline completo de hoje: busca -> normaliza -> pontua.

    Fica junto ao invés de em módulo próprio porque hoje é só isso: cada
    etapa (collector, scoring) continua isolada e testável sozinha, isso
    aqui só encadeia as chamadas.
    """
    crus = buscar_produtos_raw(query)
    produtos = [normalizar(item) for item in crus]
    precos = [p.price for p in produtos]

    itens = []
    for item_cru, produto in zip(crus, produtos):
        score = calcular_deal_score(produto, precos)
        motivo = gerar_motivo(produto, precos)
        original = extrair_preco_original(item_cru) or produto.price
        itens.append(
            ReviewItem(
                product=produto,
                score=score,
                reason=motivo,
                original_price=original,
            )
        )
    return itens


@app.get("/")
def review(request: Request, q: str = QUERY_PADRAO):
    erro = None
    review_items: list[ReviewItem] = []
    try:
        review_items = montar_review_items(q)
    except requests.RequestException as exc:
        # Falha de rede/API não deveria derrubar a página inteira, só
        # mostrar o que aconteceu. Isso é robustez básica de quem chama uma
        # fonte externa, não overengineering.
        erro = f"Não deu pra buscar produtos agora: {exc}"

    items = [
        {
            "product": item.product,
            "score": item.score,
            "reason": item.reason,
            "score_class": score_class(item.score),
            "price_current": format_price(item.product.price),
            "price_original": format_price(item.original_price),
            "message": generate_message(item),
        }
        for item in review_items
    ]

    return templates.TemplateResponse(
        request,
        "review.html",
        {"items": items, "query": q, "erro": erro},
    )
