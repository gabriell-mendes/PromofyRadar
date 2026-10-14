"""Fonte: Shopee Affiliate Open API (Brasil).

Fonte escolhida para o MVP — ver docs/decisao-fonte-de-dados.md para a
comparação completa com as alternativas investigadas (Mercado Livre,
AliExpress, Amazon).

Resumo do mecanismo (documentado em
https://www.affiliateshopee.com.br/documentacao, API oficial da Shopee
Brasil para afiliados):

- Endpoint único, GraphQL: POST https://open-api.affiliate.shopee.com.br/graphql
- Autenticação por assinatura, sem OAuth: o header `Authorization` é
  `SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={signature}`,
  onde `signature = sha256(app_id + timestamp + payload_json + app_secret)`
  (concatenação direta, sem separador, hash em hexadecimal).
- A operação usada aqui é `productOfferV2`, que permite buscar por palavra-
  chave e ordenar por preço/vendas/comissão — exatamente os dados que
  precisamos pro Deal Score (ver app/scoring.py).
- Pré-requisito: `app_id`/`app_secret` só existem depois de (1) virar
  afiliado Shopee aprovado e (2) pedir liberação de API via formulário de
  suporte do painel de afiliado — isso é uma ação que só o dono da conta pode
  fazer (cadastro pessoal), não algo automatizável por este código.

IMPORTANTE — mesma ressalva que o collector do Mercado Livre já tinha: os
nomes de campo abaixo (itemId, productName, price, priceMin, priceMax,
priceDiscountRate, imageUrl, offerLink, shopName, sales) são os
documentados publicamente, mas ESTE CÓDIGO AINDA NÃO FOI VALIDADO contra
uma resposta real da API, porque não há app_id/app_secret configurados
neste ambiente. Antes de usar em produção: rodar
`python -m app.sources.shopee "notebook"` com as credenciais reais no
.env e conferir o JSON cru contra o que normalizar() espera — ajustando
os nomes de campo se a API real divergir da documentação.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from ..models import Product
from .base import OfferSource, OfferSourceError

logger = logging.getLogger(__name__)

GRAPHQL_URL_PADRAO = "https://open-api.affiliate.shopee.com.br/graphql"

_QUERY = """
query BuscarOfertas($keyword: String, $limit: Int, $page: Int) {
  productOfferV2(keyword: $keyword, limit: $limit, page: $page, sortType: 2) {
    nodes {
      itemId
      productName
      imageUrl
      offerLink
      price
      priceMin
      priceMax
      priceDiscountRate
      sales
      shopName
    }
  }
}
"""


def _para_decimal(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


class ShopeeSource(OfferSource):
    name = "shopee"

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
        graphql_url: str | None = None,
        min_interval_seconds: float | None = None,
    ):
        self.app_id = app_id or os.environ.get("SHOPEE_APP_ID")
        self.app_secret = app_secret or os.environ.get("SHOPEE_APP_SECRET")
        self.graphql_url = graphql_url or os.environ.get(
            "SHOPEE_GRAPHQL_URL", GRAPHQL_URL_PADRAO
        )
        self.min_interval_seconds = (
            min_interval_seconds
            if min_interval_seconds is not None
            else float(os.environ.get("SHOPEE_MIN_INTERVAL_SECONDS", "1.0"))
        )
        self._ultima_chamada: float = 0.0

    def _assinar(self, payload_json: str) -> tuple[str, str]:
        timestamp = str(int(time.time()))
        base = f"{self.app_id}{timestamp}{payload_json}{self.app_secret}"
        assinatura = hashlib.sha256(base.encode("utf-8")).hexdigest()
        return timestamp, assinatura

    def _respeitar_rate_limit(self) -> None:
        """Limitador simples de 1 processo: garante um intervalo mínimo
        entre chamadas. Não coordena múltiplos processos/instâncias — não é
        necessário pro MVP (um único collector rodando de cada vez), ver
        docs/roadmap.md caso isso mude.
        """
        decorrido = time.monotonic() - self._ultima_chamada
        se_faltar = self.min_interval_seconds - decorrido
        if se_faltar > 0:
            time.sleep(se_faltar)
        self._ultima_chamada = time.monotonic()

    def buscar_produtos_raw(self, query: str, limit: int = 20) -> list[dict]:
        if not self.app_id or not self.app_secret:
            raise OfferSourceError(
                "SHOPEE_APP_ID / SHOPEE_APP_SECRET não configurados. Isso exige "
                "virar afiliado Shopee aprovado e pedir liberação de API pelo "
                "painel de afiliado — ver docs/decisao-fonte-de-dados.md."
            )

        import json

        variaveis = {"keyword": query, "limit": limit, "page": 1}
        corpo = {"query": _QUERY, "variables": variaveis}
        payload_json = json.dumps(corpo, separators=(",", ":"))
        timestamp, assinatura = self._assinar(payload_json)

        self._respeitar_rate_limit()
        try:
            resposta = requests.post(
                self.graphql_url,
                data=payload_json,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": (
                        f"SHA256 Credential={self.app_id}, "
                        f"Timestamp={timestamp}, Signature={assinatura}"
                    ),
                },
                timeout=10,
            )
        except requests.Timeout as exc:
            raise OfferSourceError(f"Timeout ao consultar Shopee: {exc}") from exc
        except requests.RequestException as exc:
            raise OfferSourceError(f"Falha de rede ao consultar Shopee: {exc}") from exc

        if resposta.status_code == 429 or (
            resposta.status_code >= 400 and b"10030" in resposta.content
        ):
            raise OfferSourceError(
                "Rate limit da Shopee atingido (erro 10030) — tente novamente "
                "mais tarde ou aumente SHOPEE_MIN_INTERVAL_SECONDS."
            )

        try:
            resposta.raise_for_status()
        except requests.HTTPError as exc:
            raise OfferSourceError(
                f"Shopee retornou erro HTTP {resposta.status_code}: {resposta.text[:300]}"
            ) from exc

        dados = resposta.json()
        if dados.get("errors"):
            raise OfferSourceError(f"Shopee retornou erro GraphQL: {dados['errors']}")

        produto_offer = (dados.get("data") or {}).get("productOfferV2") or {}
        return produto_offer.get("nodes") or []

    def normalizar(self, item_cru: dict) -> Product:
        item_id = item_cru.get("itemId")
        if not item_id:
            raise ValueError("item sem itemId")

        preco = _para_decimal(item_cru.get("price"))
        if preco is None or preco <= 0:
            raise ValueError(f"produto sem preço válido: itemId={item_id!r}")

        url = item_cru.get("offerLink")
        if not url:
            raise ValueError(f"produto sem link de oferta: itemId={item_id!r}")

        original_price = _para_decimal(item_cru.get("priceMax"))
        if original_price is not None and original_price <= preco:
            # priceMax igual (ou menor, por inconsistência da fonte) ao preço
            # atual não representa um desconto real — não exibir como "de/por"
            # enganoso (mesmo cuidado que o Mercado Livre já tinha).
            original_price = None

        sales = item_cru.get("sales")
        sales_int = int(sales) if isinstance(sales, (int, float)) else None

        return Product(
            source=self.name,
            source_id=str(item_id),
            title=item_cru.get("productName") or "(sem título)",
            price=preco,
            original_price=original_price,
            url=url,
            image_url=item_cru.get("imageUrl"),
            store=item_cru.get("shopName") or "Loja não identificada",
            sales=sales_int,
            collected_at=datetime.now(),
        )


if __name__ == "__main__":
    # python -m app.sources.shopee "notebook"
    # Rodar direto assim é o jeito mais rápido de validar os nomes de campo
    # contra uma resposta real, com SHOPEE_APP_ID/SHOPEE_APP_SECRET no ambiente.
    import json
    import sys

    logging.basicConfig(level=logging.INFO)
    consulta = sys.argv[1] if len(sys.argv) > 1 else "notebook"
    fonte = ShopeeSource()
    crus = fonte.buscar_produtos_raw(consulta, limit=3)
    print(f"{len(crus)} resultado(s) crus para {consulta!r}\n")
    if crus:
        print("Primeiro resultado cru (JSON completo, pra conferir os campos):")
        print(json.dumps(crus[0], indent=2, ensure_ascii=False))
        print()
        print("Depois de normalizar:")
        print(fonte.normalizar(crus[0]))
