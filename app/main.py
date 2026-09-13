"""Dashboard de revisão manual.

Serve UMA única página: a lista de ofertas já coletadas e pontuadas,
esperando que você (Gabriel) decida quais publicar. É a interface para a
etapa "revisão manual" que já está no MVP (docs/roadmap.md).

Hoje os dados vêm de app/mock_data.py (fictícios). Quando o collector e o
Deal Score reais existirem, a única coisa que muda aqui é de onde a lista
`items` vem — o resto (rotas, template) continua igual.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .message import format_price, generate_message
from .mock_data import MOCK_REVIEW_ITEMS

# BASE_DIR aponta para a raiz do projeto, não para app/, para que
# "uvicorn app.main:app" funcione não importa de qual pasta você rode o
# comando.
BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Grupo de Ofertas — Revisão Manual")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def score_class(score: int) -> str:
    """Classe CSS pra colorir o score — regra simples, sem mágica."""
    if score >= 70:
        return "score-good"
    if score >= 50:
        return "score-mid"
    return "score-bad"


@app.get("/")
def review(request: Request):
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
        for item in MOCK_REVIEW_ITEMS
    ]
    # A partir do Starlette 1.x, "request" é o primeiro argumento
    # posicional do TemplateResponse — não fica mais dentro do dict de
    # contexto (a assinatura antiga, TemplateResponse(nome, {"request": ...}),
    # foi removida).
    return templates.TemplateResponse(
        request,
        "review.html",
        {"items": items},
    )
