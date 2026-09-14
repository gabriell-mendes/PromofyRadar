"""Collector: fala com a API pública do Mercado Livre.

Única responsabilidade desta camada: buscar produtos crus (no formato da
fonte) e normalizá-los em Product. Não decide nada sobre a oferta ser boa
ou não, isso é trabalho de app/scoring.py, que nem sabe de onde o Product
veio. Ver docs/architecture.md, seção "por que separar collector /
normalização / análise".

Sem autenticação: a busca da API do Mercado Livre é pública.

IMPORTANTE: os nomes de campo abaixo (title, price, permalink, seller,
original_price) são o formato conhecido da API pública de busca do Mercado
Livre, mas ainda NÃO foram validados contra a API ao vivo.

Testado em 2026-09-13: `/sites/MLB/search` retorna 403 Forbidden mesmo com
header User-Agent presente. O corpo do erro é
`{"message":"forbidden","error":"forbidden","status":403,"cause":[]}`,
vindo do próprio backend do Mercado Livre (não é bloqueio de CDN/WAF nem
coisa de rede local). Há vários relatos de outros desenvolvedores em 2026
com o mesmo sintoma nesse endpoint específico, inclusive com access_token
OAuth válido (outros endpoints como /users/me funcionam normalmente) — ver
threads no Reclame Aqui sobre "403 /sites/MLB/search". Ou seja, isso não é
um problema de header/User-Agent: o endpoint parece estar bloqueado para
apps de terceiros em geral, possivelmente exigindo cadastro no programa de
parceiros de desenvolvedor do Mercado Livre ou algum outro tipo de
liberação não documentada publicamente.

Próximo passo antes de seguir com este collector: confirmar com a
documentação/suporte do Mercado Livre se `/sites/MLB/search` exige
autenticação OAuth ou whitelist, ou considerar uma fonte de dados
alternativa. Só depois disso faz sentido validar os nomes de campo em
normalizar() e extrair_preco_original() abaixo contra uma resposta real.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from .models import Product

BASE_URL = "https://api.mercadolibre.com/sites/MLB/search"


def buscar_produtos_raw(query: str, limit: int = 10) -> list[dict]:
    """Busca produtos no formato cru da API, sem transformar nada."""
    resposta = requests.get(
        BASE_URL,
        params={"q": query, "limit": limit},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
        },
        timeout=10,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    return dados.get("results", [])


def _para_decimal(valor) -> Decimal | None:
    """Converte um número vindo do JSON pra Decimal, sem o erro de
    arredondamento de ponto flutuante que Decimal(valor_float) direto teria.
    """
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def normalizar(item_cru: dict) -> Product:
    """Converte um item cru da API num Product padronizado."""
    seller = item_cru.get("seller") or {}
    return Product(
        source="mercadolivre",
        source_id=str(item_cru.get("id", "")),
        title=item_cru.get("title", "(sem título)"),
        price=_para_decimal(item_cru.get("price")) or Decimal("0"),
        url=item_cru.get("permalink", ""),
        store=seller.get("nickname") or "Loja não identificada",
        collected_at=datetime.now(),
    )


def extrair_preco_original(item_cru: dict) -> Decimal | None:
    """Pega o "preço de antes" que a própria loja anuncia (quando existe).

    Cuidado: isso é o desconto que a LOJA afirma, exatamente o tipo de
    número que o projeto não quer usar sozinho pra decidir se a oferta é
    boa (ver docs/roadmap.md). Aqui ele só serve pra mostrar "de X por Y" na
    mensagem, de forma transparente. O Deal Score (app/scoring.py) nunca
    usa esse valor, só compara com os outros preços da mesma busca.
    """
    return _para_decimal(item_cru.get("original_price"))


def buscar_produtos(query: str, limit: int = 10) -> list[Product]:
    """Busca e normaliza numa chamada só."""
    crus = buscar_produtos_raw(query, limit)
    return [normalizar(item) for item in crus]


if __name__ == "__main__":
    # python -m app.collector "notebook"
    # Rodar direto assim (sem subir o servidor) é o jeito mais rápido de
    # validar contra a API real e ver o formato de verdade dos dados.
    import sys

    consulta = sys.argv[1] if len(sys.argv) > 1 else "notebook"
    crus = buscar_produtos_raw(consulta, limit=3)
    print(f"{len(crus)} resultado(s) crus para {consulta!r}\n")
    if crus:
        print("Primeiro resultado cru (JSON completo, pra conferir os campos):")
        import json

        print(json.dumps(crus[0], indent=2, ensure_ascii=False))
        print()
        print("Depois de normalizar:")
        print(normalizar(crus[0]))
        print("preço original extraído:", extrair_preco_original(crus[0]))
