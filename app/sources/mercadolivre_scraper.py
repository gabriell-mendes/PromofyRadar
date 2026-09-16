"""Fonte: Mercado Livre via scraping (Playwright + BeautifulSoup).

Substitui, na prática, app/sources/mercadolivre.py (a API oficial, que fica
mantida só como referência histórica sob a chave "mercadolivre_api" em
app/config.py — ver o motivo do bloqueio dela em docs/decisao-fonte-de-dados.md).

Decisão de arquitetura (2026-09-15, ver memória do projeto): em vez de
esperar uma API oficial, essa fonte simula um navegador real pra ler a
página pública de BUSCA do Mercado Livre e extrai os dados do HTML
renderizado. Isso segue o mesmo padrão de 3 etapas usado em qualquer
scraper (download -> extract -> output), só que aqui como três funções
simples dentro de um arquivo só, não como classes/pastas separadas:

1. download  -> _baixar_html_busca(): abre o Playwright, navega até a
   busca, devolve o HTML puro. Não sabe o que é "preço" ou "título".
2. extract   -> _extrair_itens_crus(): usa SELECTORS pra cortar os campos
   do HTML. Ainda devolve texto cru (ex: "1.299" e "00" separados).
3. output    -> normalizar(): já exigido pela interface OfferSource,
   converte o texto cru em Product (preço vira Decimal de verdade).

Reaproveita de app/sources/mercadolivre_page.py (o scraper de página de
PRODUTO único, já validado por Gabriel): _clean (limpeza de espaço),
_money (texto "1.299" + "00" -> Decimal), _item_id (extrai o código MLB de
uma URL) e _block_reason (detecta página de verificação/captcha na hora,
pra parar em vez de tentar contornar — ver princípio do projeto de não
burlar anti-bot).

IMPORTANTE, mesma ressalva de sempre com scraping: o Mercado Livre muda o
HTML da página de busca com uma certa frequência. Os seletores abaixo
partem do projeto de referência github.com/ipseitycode/web-scraping
(ver docs/decisao-fonte-de-dados.md), mas NÃO foram validados contra o
site real nesta sessão — quem tem acesso ao navegador real é você.
Rode este arquivo direto (ver bloco no final) contra uma busca de verdade
antes de confiar nos dados. Se um campo vier sempre None, o seletor
provavelmente mudou: abra a página, aperte F12, e ajuste o valor
correspondente em SELECTORS.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from decimal import Decimal

from bs4 import BeautifulSoup
from bs4.element import Tag
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ..models import Product
from .base import OfferSource, OfferSourceError
from .mercadolivre_page import _block_reason, _clean, _item_id, _money

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 30_000
URL_BASE = "https://lista.mercadolivre.com.br"

# Ponto único de manutenção dos seletores: se o Mercado Livre mudar o
# layout, é aqui (e só aqui) que se mexe. Cada valor é uma tupla de
# seletores alternativos, testados em ordem — o primeiro que existir no
# card é usado. Isso segue o mesmo estilo de mercadolivre_page.py.
#
# O preço (atual/anterior) não está aqui porque não é um simples "pega o
# primeiro que existir": o Mercado Livre usa a MESMA classe CSS
# (andes-money-amount__fraction) tanto pro preço atual quanto pro
# riscado/anterior, e a única forma confiável de diferenciar é checar se o
# elemento está dentro de um <s class="andes-money-amount--previous">. Essa
# lógica fica em _preco_atual/_preco_anterior, não dá pra reduzir a uma
# string de seletor sem correr o risco de pegar o preço errado quando o
# produto está com desconto (foi exatamente o que aconteceu no projeto de
# referência que usamos como ponto de partida).
SELECTORS: dict[str, tuple[str, ...]] = {
    "item": ("li.ui-search-layout__item",),
    "title": ("a.poly-component__title",),
    "seller": ("span.poly-component__seller",),
    "shipping": ("div.poly-component__shipping", "div.poly-component__shipping-v2"),
}

_PREVIOUS_PRICE_SELECTOR = "s.andes-money-amount--previous"
_MONEY_CONTAINER_SELECTOR = ".andes-money-amount"
_FRACTION_SELECTOR = ".andes-money-amount__fraction"
_CENTS_SELECTOR = ".andes-money-amount__cents"


def _first_match(card: Tag, selectors: tuple[str, ...]) -> Tag | None:
    for selector in selectors:
        found = card.select_one(selector)
        if found is not None:
            return found
    return None


def _money_from_container(container: Tag | None) -> Decimal | None:
    """Lê fração + centavos de dentro de UM container de preço já
    localizado (ex: o <span class="andes-money-amount"> atual, ou o <s>
    do preço anterior) e devolve como Decimal, reaproveitando _money().
    """
    if container is None:
        return None
    fraction_el = container.select_one(_FRACTION_SELECTOR)
    if fraction_el is None:
        return None
    cents_el = container.select_one(_CENTS_SELECTOR)
    fraction_text = _clean(fraction_el.get_text())
    cents_text = _clean(cents_el.get_text()) if cents_el else None
    return _money(fraction_text, cents_text)


def _preco_anterior(card: Tag) -> Decimal | None:
    """Preço "de", riscado. Fica dentro de <s class="andes-money-amount--previous">."""
    container = card.select_one(_PREVIOUS_PRICE_SELECTOR)
    return _money_from_container(container)


def _preco_atual(card: Tag) -> Decimal | None:
    """Preço "por", o que o card está cobrando agora.

    Cuidado que vale a pena entender: o card pode ter DOIS blocos de preço
    (anterior e atual), e os dois usam a mesma classe de fração. Por isso
    aqui a gente varre todos os containers de preço do card e pula
    qualquer um que esteja DENTRO do <s> do preço anterior, em vez de
    simplesmente pegar "o primeiro andes-money-amount__fraction que
    aparecer" (isso pegaria o preço errado sempre que o card tiver
    desconto, dependendo da ordem em que o Mercado Livre desenha os dois
    blocos no HTML).
    """
    for container in card.select(_MONEY_CONTAINER_SELECTOR):
        if container.find_parent("s", class_="andes-money-amount--previous"):
            continue
        preco = _money_from_container(container)
        if preco is not None:
            return preco
    return None


def _baixar_html_busca(
    query: str, *, headed: bool = False, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> str:
    """Passo 1 (download): abre a busca no Mercado Livre em Chromium normal
    e devolve o HTML renderizado. Não interpreta nada do conteúdo.
    """
    termo = "-".join(query.strip().lower().split())
    url = f"{URL_BASE}/{termo}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        try:
            context = browser.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo")
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            logger.info("Abrindo busca: %s", url)
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if response and response.status >= 400:
                raise OfferSourceError(f"Busca respondeu com HTTP {response.status}.")

            try:
                page.locator(SELECTORS["item"][0]).first.wait_for(
                    state="visible", timeout=min(timeout_ms, 12_000)
                )
            except PlaywrightTimeoutError:
                # Pode ser busca sem resultado nenhum, página de bloqueio,
                # ou o seletor mudou — não decide sozinho, só loga e deixa
                # o _block_reason abaixo (e a extração vazia depois)
                # contarem a história pra quem chamou.
                logger.info("Nenhum item visível no tempo esperado; inspecionando a página")

            if reason := _block_reason(page):
                raise OfferSourceError(f"Bloqueio/verificação detectado na busca: {reason}")

            return page.content()
        finally:
            browser.close()


def _extrair_itens_crus(html: str) -> list[dict]:
    """Passo 2 (extract): aplica SELECTORS sobre o HTML já baixado.

    Recebe uma STRING (não precisa de navegador aberto), o que faz dessa
    função fácil de testar sozinha: dá pra salvar um HTML de exemplo num
    arquivo e chamar _extrair_itens_crus(html_salvo) num teste, sem precisar
    do Playwright.
    """
    soup = BeautifulSoup(html, "html.parser")
    itens: list[dict] = []

    for card in soup.select(SELECTORS["item"][0]):
        title_el = _first_match(card, SELECTORS["title"])
        if title_el is None:
            # Card sem título reconhecível: normalmente é propaganda/banner
            # misturado na listagem, não um produto de verdade. Pula em vez
            # de derrubar a busca inteira por causa de UM card estranho.
            continue

        seller_el = _first_match(card, SELECTORS["seller"])

        itens.append(
            {
                "title": _clean(title_el.get_text()),
                "url": title_el.get("href"),
                "current_price": _preco_atual(card),
                "previous_price": _preco_anterior(card),
                "seller": _clean(seller_el.get_text()) if seller_el else None,
            }
        )

    return itens


class MercadoLivreScraperSource(OfferSource):
    name = "mercadolivre"

    def __init__(
        self,
        *,
        headed: bool = False,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        min_interval_seconds: float | None = None,
    ):
        self.headed = headed
        self.timeout_ms = timeout_ms
        self.min_interval_seconds = (
            min_interval_seconds
            if min_interval_seconds is not None
            else float(os.environ.get("MERCADOLIVRE_MIN_INTERVAL_SECONDS", "2.0"))
        )
        self._ultima_chamada: float = 0.0

    def _respeitar_rate_limit(self) -> None:
        """Mesmo limitador simples de 1 processo que o ShopeeSource já usa
        (ver app/sources/shopee.py). Scraping com navegador é mais pesado
        que uma chamada de API, então o intervalo padrão aqui é maior.
        """
        decorrido = time.monotonic() - self._ultima_chamada
        se_faltar = self.min_interval_seconds - decorrido
        if se_faltar > 0:
            time.sleep(se_faltar)
        self._ultima_chamada = time.monotonic()

    def buscar_produtos_raw(self, query: str, limit: int = 20) -> list[dict]:
        self._respeitar_rate_limit()
        try:
            html = _baixar_html_busca(query, headed=self.headed, timeout_ms=self.timeout_ms)
        except OfferSourceError:
            raise
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            # Nunca deixar a exceção nativa do Playwright vazar pra fora da
            # fonte — quem chama (app/main.py) só conhece OfferSourceError.
            raise OfferSourceError(
                f"Falha ao carregar a busca do Mercado Livre: {exc}"
            ) from exc

        itens = _extrair_itens_crus(html)
        return itens[:limit]

    def normalizar(self, item_cru: dict) -> Product:
        preco = item_cru.get("current_price")
        if preco is None or preco <= 0:
            raise ValueError(f"produto sem preço atual válido: {item_cru.get('url')!r}")

        url = item_cru.get("url")
        if not url:
            raise ValueError("produto sem link")

        original_price = item_cru.get("previous_price")
        if original_price is not None and original_price <= preco:
            # Mesma regra que as outras fontes já seguem: preço "de" igual
            # ou menor que o atual não é desconto real, não mostrar como se
            # fosse (evita "de R$100 por R$100" ou "de/por" invertido por
            # erro de leitura do HTML).
            original_price = None

        return Product(
            source=self.name,
            source_id=_item_id(url) or url,
            title=item_cru.get("title") or "(sem título)",
            price=preco,
            original_price=original_price,
            url=url,
            store=item_cru.get("seller") or "Loja não identificada",
            collected_at=datetime.now(),
        )


if __name__ == "__main__":
    # python -m app.sources.mercadolivre_scraper "notebook" --headed --verbose
    #
    # Rodar isso é o jeito mais rápido de validar se os seletores em
    # SELECTORS ainda batem com o site real. --headed abre o navegador
    # visível (mais fácil de ver o que está acontecendo se algo vier
    # None); --verbose mostra os logs de INFO/DEBUG.
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Testa a busca por scraping no Mercado Livre com dados reais."
    )
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--headed", action="store_true", help="Mostra a janela do navegador")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    fonte = MercadoLivreScraperSource(headed=args.headed)

    print(f"Buscando {args.query!r} no Mercado Livre (scraping real)...\n")
    crus = fonte.buscar_produtos_raw(args.query, limit=args.limit)
    print(f"{len(crus)} item(ns) cru(s) extraído(s).\n")

    if not crus:
        print(
            "Nenhum item extraído. Prováveis causas: o seletor SELECTORS['item'] "
            "mudou, a busca não teve resultado, ou a página caiu num bloqueio "
            "(rode de novo com --headed --verbose pra ver o que aconteceu)."
        )
    else:
        print("Primeiro item cru (antes de normalizar):")
        print(
            json.dumps(
                {k: (str(v) if v is not None else None) for k, v in crus[0].items()},
                indent=2,
                ensure_ascii=False,
            )
        )
        print("\nDepois de normalizar (o que sobrevive a normalizar()):")
        for produto in fonte.buscar_produtos(args.query, limit=args.limit):
            de = f"R$ {produto.original_price}" if produto.original_price else "-"
            print(f"- {produto.title}")
            print(f"  De {de} por R$ {produto.price} | {produto.store} | {produto.url}")
