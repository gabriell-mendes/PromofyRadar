"""Fonte: Mercado Livre — DESATIVADA por decisão de arquitetura.

Ver docs/decisao-fonte-de-dados.md para a investigação completa. Resumo:

`api.mercadolibre.com/sites/MLB/search` retorna 403 com o corpo
`{"message":"forbidden","error":"forbidden","status":403,"cause":[]}` e o
código interno `PA_UNAUTHORIZED_RESULT_FROM_POLICIES` (bloqueio de um
"PolicyAgent" do próprio backend do Mercado Livre) para QUALQUER chamada
de terceiro — testado com script (Python/requests), com OAuth (token
válido, que funciona normalmente em /users/me), e com um Chrome real via
Claude in Chrome (fingerprint TLS diferente de script). O mesmo bloqueio
aparece em relatos de outros desenvolvedores independentes no Reclame
Aqui, incluindo uma resposta oficial do Mercado Livre direcionando o caso
para "canais de suporte especializados para desenvolvedores e parceiros
certificados" — ou seja, existe uma trilha de acesso, mas não é self-service
nem documentada publicamente; depende de certificação/contato direto com o
Mercado Livre, sem prazo ou critério conhecido.

Isso NÃO é um problema de header, User-Agent, IP ou fingerprint — logo,
não é algo que se resolve com proxy, rotação de IP, outro cliente HTTP ou
stealth de navegador. Esta classe existe pra manter a lógica de
normalização pronta (caso a certificação de parceiro um dia aconteça) sem
gastar uma chamada de rede contra um endpoint que sabemos, com alta
confiança, que vai devolver 403. Ela levanta SourceUnavailableError
imediatamente em vez de tentar a requisição.

Para reavaliar manualmente (ex: depois de obter certificação de parceiro),
chame com `forcar_tentativa=True` — só nesse caso a chamada HTTP real é
feita.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from ..models import Product
from .base import OfferSource, OfferSourceError, SourceUnavailableError

BASE_URL = "https://api.mercadolibre.com/sites/MLB/search"

_MOTIVO_BLOQUEIO = (
    "Mercado Livre desativado como fonte: api.mercadolibre.com/sites/MLB/search "
    "responde 403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES pra qualquer app de "
    "terceiro (confirmado com script, OAuth e navegador real). Requer "
    "certificação de parceiro não self-service. Ver docs/decisao-fonte-de-dados.md."
)


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


class MercadoLivreSource(OfferSource):
    # Nome trocado pra "mercadolivre_api" (2026-09-16, ver app/config.py):
    # "mercadolivre" sozinho agora aponta pra MercadoLivreScraperSource, que
    # é a fonte que de fato roda. Esta classe fica só como referência caso a
    # certificação de parceiro do Mercado Livre um dia se torne viável.
    name = "mercadolivre_api"

    def __init__(self, forcar_tentativa: bool = False):
        self.forcar_tentativa = forcar_tentativa

    def buscar_produtos_raw(self, query: str, limit: int = 20) -> list[dict]:
        if not self.forcar_tentativa:
            raise SourceUnavailableError(_MOTIVO_BLOQUEIO)

        try:
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
        except requests.RequestException as exc:
            raise OfferSourceError(f"Falha ao consultar Mercado Livre: {exc}") from exc

        return resposta.json().get("results", [])

    def normalizar(self, item_cru: dict) -> Product:
        """Converte um item cru da API num Product padronizado.

        Mantido validado contra o FORMATO DOCUMENTADO da API (title, price,
        permalink, seller, original_price) — mas, como registrado acima,
        isso nunca foi validado contra uma resposta real, porque o endpoint
        está bloqueado desde antes da primeira tentativa bem-sucedida.
        """
        preco = _para_decimal(item_cru.get("price"))
        if preco is None or preco <= 0:
            raise ValueError(f"produto sem preço válido: {item_cru.get('id')!r}")

        url = item_cru.get("permalink")
        if not url:
            raise ValueError(f"produto sem link: {item_cru.get('id')!r}")

        seller = item_cru.get("seller") or {}
        return Product(
            source=self.name,
            source_id=str(item_cru.get("id", "")),
            title=item_cru.get("title", "(sem título)"),
            price=preco,
            original_price=_para_decimal(item_cru.get("original_price")),
            url=url,
            image_url=item_cru.get("thumbnail"),
            store=seller.get("nickname") or "Loja não identificada",
            collected_at=datetime.now(),
        )
