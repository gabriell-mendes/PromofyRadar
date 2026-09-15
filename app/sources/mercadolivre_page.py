"""Coleta de uma URL individual do Mercado Livre, sem evasão de bloqueios."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ..models import Product
from .base import OfferSourceError

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_MS = 30_000


class ProductPageBlockedError(OfferSourceError):
    """A página aberta é uma verificação/bloqueio; a coleta deve parar."""


@dataclass
class MercadoLivrePage:
    status: str
    scraped_at: str
    source_url: str
    final_url: str | None = None
    item_id: str | None = None
    title: str | None = None
    price: Decimal | None = None
    previous_price: Decimal | None = None
    availability: str | None = None
    seller: str | None = None
    image_urls: list[str] | None = None
    warnings: list[str] | None = None
    error: str | None = None

    def as_json_dict(self) -> dict:
        data = asdict(self)
        for field in ("price", "previous_price"):
            if data[field] is not None:
                data[field] = float(data[field])
        return data

    def to_product(self) -> Product:
        """Adaptador opcional para o Product usado pelo pipeline do projeto."""
        if self.status != "ok" or not all((self.item_id, self.title, self.price, self.final_url)):
            raise ValueError("A coleta não contém os campos necessários para criar Product.")
        return Product(
            source="mercadolivre", source_id=self.item_id, title=self.title,
            price=self.price, original_price=self.previous_price, url=self.final_url,
            store=self.seller or "Loja não identificada", image_url=(self.image_urls or [None])[0],
            collected_at=datetime.now(),
        )


def _clean(value: str | None) -> str | None:
    return re.sub(r"\s+", " ", value).strip() if value and value.strip() else None


def _money(fraction: str | None, cents: str | None) -> Decimal | None:
    integer = re.sub(r"\D", "", _clean(fraction) or "")
    decimals = re.sub(r"\D", "", cents or "")[:2]
    if not integer:
        return None
    try:
        return Decimal(f"{integer}.{decimals}") if decimals else Decimal(integer)
    except InvalidOperation:
        return None


def _item_id(url: str) -> str | None:
    match = re.search(r"\b(MLB[- ]?\d{6,})\b", url, re.I)
    return match.group(1).replace("-", "").upper() if match else None


def _first_text(page, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.count():
                value = _clean(element.inner_text(timeout=1_500))
                if value:
                    return value
        except (PlaywrightError, PlaywrightTimeoutError):
            continue
    return None


def _first_attr(page, selectors: tuple[str, ...], name: str) -> str | None:
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.count() and (value := element.get_attribute(name, timeout=1_500)):
                return value
        except (PlaywrightError, PlaywrightTimeoutError):
            continue
    return None


def _block_reason(page) -> str | None:
    title = page.title().lower()
    body = page.locator("body").inner_text(timeout=3_000).lower()
    for signal in (
        "verifique se você é humano", "verificação de segurança", "access denied", "captcha",
        "unusual traffic", "just a moment", "checking your browser", "temporarily blocked",
    ):
        if signal in title or signal in body:
            return f"Página de bloqueio/verificação detectada ({signal!r})."
    if "mercadolivre" not in page.url.lower() and "mercadolibre" not in page.url.lower():
        return "A página redirecionou para fora do Mercado Livre."
    return None


def _image_urls(page) -> list[str]:
    results: list[str] = []
    for selector in ("figure.ui-pdp-gallery__figure img", ".ui-pdp-gallery__figure img", "img[data-zoom]", "meta[property='og:image']"):
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 20)):
                node = locator.nth(index)
                value = node.get_attribute("content") or node.get_attribute("data-zoom") or node.get_attribute("src")
                if value and value.startswith(("https://", "http://")) and value not in results:
                    results.append(value)
        except PlaywrightError:
            continue
    return results


def collect_product_page(url: str, *, headed: bool = False, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> MercadoLivrePage:
    """Carrega uma URL em Chromium normal; não tenta superar bloqueios."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("A URL precisa ser absoluta e começar com http:// ou https://.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        try:
            context = browser.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo")
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            logger.info("Abrindo página de produto")
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if response and response.status >= 400:
                raise OfferSourceError(f"A página respondeu com HTTP {response.status}.")
            try:
                page.locator("h1").first.wait_for(state="visible", timeout=min(timeout_ms, 12_000))
            except PlaywrightTimeoutError:
                logger.info("Nenhum h1 visível no tempo esperado; inspecionando a página")
            if reason := _block_reason(page):
                raise ProductPageBlockedError(reason)

            title = _first_text(page, ("h1.ui-pdp-title", "h1"))
            current_fraction = _first_text(page, (".ui-pdp-price__second-line .andes-money-amount__fraction", ".andes-money-amount__fraction"))
            current_cents = _first_text(page, (".ui-pdp-price__second-line .andes-money-amount__cents", ".andes-money-amount__cents"))
            previous_fraction = _first_text(page, (".ui-pdp-price__original-value .andes-money-amount__fraction", ".andes-money-amount--previous .andes-money-amount__fraction"))
            previous_cents = _first_text(page, (".ui-pdp-price__original-value .andes-money-amount__cents", ".andes-money-amount--previous .andes-money-amount__cents"))
            canonical = _first_attr(page, ("link[rel='canonical']",), "href")
            warnings = []
            if not title:
                warnings.append("Título não encontrado; o layout público pode ter mudado.")
            if not current_fraction:
                warnings.append("Preço atual não encontrado.")
            return MercadoLivrePage(
                status="ok", scraped_at=datetime.now(timezone.utc).isoformat(), source_url=url,
                final_url=page.url, item_id=_item_id(page.url) or _item_id(canonical or ""), title=title,
                price=_money(current_fraction, current_cents), previous_price=_money(previous_fraction, previous_cents),
                availability=_first_text(page, (".ui-pdp-buybox__quantity", ".ui-pdp-stock-information")),
                seller=_first_text(page, (".ui-pdp-seller__header__title", ".ui-pdp-seller__header__info-container", ".ui-pdp-seller__link-trigger-button")),
                image_urls=_image_urls(page), warnings=warnings or None,
            )
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta uma URL individual do Mercado Livre em Chromium padrão.")
    parser.add_argument("url")
    parser.add_argument("--output", type=Path, help="Arquivo JSON opcional")
    parser.add_argument("--headed", action="store_true", help="Exibe a janela normal do Chromium")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS, help="Timeout em ms (padrão: 30000)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    try:
        result, code = collect_product_page(args.url, headed=args.headed, timeout_ms=args.timeout), 0
    except ProductPageBlockedError as exc:
        result, code = MercadoLivrePage("blocked", datetime.now(timezone.utc).isoformat(), args.url, error=str(exc)), 3
    except (OfferSourceError, PlaywrightError, PlaywrightTimeoutError, ValueError) as exc:
        result, code = MercadoLivrePage("error", datetime.now(timezone.utc).isoformat(), args.url, error=str(exc)), 2
    output = json.dumps(result.as_json_dict(), ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        logger.info("Resultado salvo em %s", args.output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
