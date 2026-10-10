import asyncio
import json
import random
import logging
import urllib.parse
import os
import re
from datetime import datetime
from typing import List, Dict

from playwright.async_api import async_playwright, Page
import playwright_stealth

from pontuacao import linha_terminal, pontuar_e_ordenar

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 48  # o ML pagina de 48 em 48 resultados (offset via _Desde_)


class SmartOfferScraper:
    # Seletor dos cards de produto. Subclasses (ex: scraper_ofertas.py) podem trocar.
    ITEM_SELECTOR = ".ui-search-layout__item, [class*='search-item']"

    def __init__(self, min_discount: float = 0.0, debug: bool = False):
        self.min_discount = min_discount
        self.debug = debug
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        ]
        self.user_data_dir = os.path.join(os.getcwd(), "browser_profile")
        self.debug_dir = os.path.join(os.getcwd(), "debug_snapshots")
        if self.debug:
            os.makedirs(self.debug_dir, exist_ok=True)
        self.seen_links = set()  # evita duplicar itens entre páginas
        # TODOS os itens lidos (mesmo os cortados pelo desconto mínimo): formam o grupo
        # de comparação do Deal Score e alimentam o histórico de preços
        self.todos_vistos: List[Dict] = []

    async def _human_delay(self, min_s: float = 1.0, max_s: float = 3.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    def _clean_price_value(self, text: str) -> float:
        """Limpeza síncrona de strings monetárias (formato BR: 1.234,56)."""
        if not text:
            return 0.0
        clean_text = re.sub(r"[^\d,.]", "", text)
        if not clean_text:
            return 0.0
        if "," in clean_text and "." in clean_text:
            clean_text = clean_text.replace(".", "").replace(",", ".")
        elif "," in clean_text:
            clean_text = clean_text.replace(",", ".")
        try:
            return float(clean_text)
        except ValueError:
            return 0.0

    async def _extract_current_price(self, item) -> float:
        fraction_el = await item.query_selector(
            ".poly-price__current .andes-money-amount__fraction"
        )
        if not fraction_el:
            return 0.0
        cents_el = await item.query_selector(
            ".poly-price__current .andes-money-amount__cents"
        )
        fraction_text = await fraction_el.inner_text()
        cents_text = await cents_el.inner_text() if cents_el else "00"
        fraction_digits = re.sub(r"[^\d]", "", fraction_text)
        cents_digits = re.sub(r"[^\d]", "", cents_text) or "0"
        if not fraction_digits:
            return 0.0
        return float(fraction_digits) + (float(cents_digits) / 100)

    async def _extract_old_price(self, item) -> float:
        container = await item.query_selector(
            ".poly-price__labels, .andes-money-amount--previous"
        )
        if not container:
            return 0.0
        raw_text = await container.inner_text()
        match = re.search(r"(\d+[.,]\d{2})", raw_text)
        if match:
            return self._clean_price_value(match.group(0))
        match_int = re.search(r"(\d+)", raw_text)
        return float(match_int.group(0)) if match_int else 0.0

    async def _extract_image(self, item) -> str:
        """URL da foto do produto. O ML às vezes só carrega a imagem quando o card aparece na tela."""
        img = await item.query_selector(
            "img.poly-component__picture, .poly-card__portada img, "
            ".ui-search-result-image__element, img"
        )
        if not img:
            return ""
        for tentativa in range(2):
            for attr in ("src", "data-src", "data-lazy-src"):
                val = await img.get_attribute(attr)
                if val and val.startswith("http"):
                    return val
            srcset = await img.get_attribute("srcset")
            if srcset:
                primeira = srcset.split(",")[0].strip().split(" ")[0]
                if primeira.startswith("http"):
                    return primeira
            if tentativa == 0:
                # imagem ainda não carregou: traz o card para a tela e tenta de novo
                try:
                    await item.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass
                await self._human_delay(0.3, 0.6)
        return ""

    async def _dump_debug_html(self, page: Page, tag: str):
        if not self.debug:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.debug_dir, f"{tag}_{ts}.html")
        try:
            content = await page.content()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.warning(f"[DEBUG] HTML salvo em {path}")
        except Exception as e:
            logger.error(f"Falha ao salvar debug HTML: {e}")

    

    def _pontuar(self, resultados: List[Dict]) -> List[Dict]:
        """Calcula o Deal Score de cada oferta e ordena pela nota (ver pontuacao.py)."""
        return pontuar_e_ordenar(resultados, self.todos_vistos)

    async def _extract_items_on_page(self, page: Page) -> List[Dict]:
        """Extrai e filtra os itens visíveis na página atual (sem navegar)."""
        page_results: List[Dict] = []
        items = await page.query_selector_all(self.ITEM_SELECTOR)

        if not items:
            logger.warning("Nenhum item encontrado nesta página.")
            await self._dump_debug_html(page, "empty_items")
            return page_results

        for i, item in enumerate(items):
            try:
                title_el = await item.query_selector(
                    ".ui-search-item__title, .poly-component__title"
                )
                if not title_el:
                    continue
                title = (await title_el.inner_text()).strip()

                current_price_val = await self._extract_current_price(item)
                old_price_val = await self._extract_old_price(item)

                link_el = await item.query_selector("a")
                link = await link_el.get_attribute("href") if link_el else None
                if link and not link.startswith("http"):
                    link = f"https://www.mercadolivre.com.br{link}"
                if link:
                    # tira o "#polycard_client=...&tracking_id=..." (muda a cada busca e
                    # faria o mesmo produto parecer diferente ao deduplicar)
                    link = link.split("#")[0]

                # Sem link não dá pra deduplicar nem oferecer o produto: pula
                if not link:
                    continue
                if link in self.seen_links:
                    continue

                # Sem preço atual válido: item ilegível, pula (não inventa)
                if current_price_val <= 0:
                    logger.warning(f"[SKIP-NOPRICE] {title[:40]}...")
                    continue

                # Sem preço antigo real ou preço antigo <= atual: não há
                # desconto verificável, não simula nada
                if old_price_val <= 0 or old_price_val <= current_price_val:
                    old_price_val = current_price_val
                    actual_discount = 0.0
                else:
                    actual_discount = (
                        (old_price_val - current_price_val) / old_price_val
                    ) * 100

                installment_el = await item.query_selector(".poly-price__installments")
                installment_info = (
                    await installment_el.inner_text() if installment_el else "Consulte no site"
                )
                installment_info = " ".join(installment_info.split())
                image_url = await self._extract_image(item)

                self.seen_links.add(link)
                self.todos_vistos.append({"link": link, "price": round(current_price_val, 2)})

                if actual_discount >= self.min_discount:
                    page_results.append(
                        {
                            "title": title,
                            "price": round(current_price_val, 2),
                            "old_price": round(old_price_val, 2),
                            "discount": round(actual_discount, 2),
                            "installment": installment_info,
                            "link": link,
                            "image": image_url,
                        }
                    )
                    logger.info(
                        f"[OK] {title[:30]}... (R$ {current_price_val:.2f}, "
                        f"{actual_discount:.1f}% off)"
                    )
                else:
                    logger.info(
                        f"[SKIP] {title[:30]}... ({actual_discount:.1f}% off < mínimo)"
                    )

                await self._human_delay(0.2, 0.5)

            except Exception as e:
                logger.error(f"Erro no item {i + 1}: {e}")
                continue

        return page_results

    async def scrape_mercadolivre(self, query: str, max_pages: int = 1) -> List[Dict]:
        all_results: List[Dict] = []
        query_encoded = urllib.parse.quote(query.replace(" ", "-"))
        base_url = f"https://lista.mercadolivre.com.br/{query_encoded}"

        async with async_playwright() as p:
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False,
                user_agent=random.choice(self.user_agents),
                viewport={"width": 1280, "height": 720},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )

            page = await browser_context.new_page()

            try:
                try:
                    await playwright_stealth.stealth_async(page)
                except Exception:
                    pass

                for page_num in range(1, max_pages + 1):
                    # Navegação real por página: ML pagina via offset na URL
                    # (_Desde_51 = itens 51 em diante), não por clique de botão.
                    # Isso é bem mais robusto que localizar/clicar "Próxima".
                    offset = (page_num - 1) * ITEMS_PER_PAGE + 1
                    url = base_url if page_num == 1 else f"{base_url}_Desde_{offset}"

                    logger.info(f"--- Página {page_num} ({url}) ---")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    except Exception as e:
                        logger.warning(f"Aviso de navegação: {e}. Tentando prosseguir...")

                    

                    try:
                        await page.wait_for_selector(
                            ".ui-search-layout__item, [class*='search-item']",
                            timeout=20000,
                        )
                    except Exception:
                        logger.error(
                            f"Nenhum item apareceu na página {page_num}. "
                            "Provavelmente é o fim dos resultados."
                        )
                        await self._dump_debug_html(page, f"no_items_page{page_num}")
                        break

                    # Scroll gradual pra carregar lazy-load de imagens/preços
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await self._human_delay(1, 2)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self._human_delay(2, 3)

                    page_results = await self._extract_items_on_page(page)
                    if not page_results and not await page.query_selector(
                        ".ui-search-layout__item, [class*='search-item']"
                    ):
                        # página sem itens de verdade -> fim da paginação
                        break

                    all_results.extend(page_results)
                    await self._human_delay(1.5, 3)

                self._pontuar(all_results)

            except Exception as e:
                logger.error(f"Erro crítico no loop: {e}")
                await self._dump_debug_html(page, "critical_error")
            finally:
                await browser_context.close()

        return all_results


async def main():
    print("=" * 40)
    print(" SCRAPER DE OFERTAS - MERCADO LIVRE ")
    print("=" * 40)

    query = input(" Digite o produto que deseja buscar: ").strip()
    try:
        min_discount_input = input(" Desconto mínimo desejado (ex: 10): ").strip()
        min_discount = float(min_discount_input) if min_discount_input else 0.0
    except ValueError:
        min_discount = 0.0

    try:
        max_pages = int(input(" Quantas páginas navegar? (ex: 3): ") or 1)
    except ValueError:
        max_pages = 1

    debug_input = input(" Salvar HTML de debug em caso de falha? (s/N): ").strip().lower()
    debug = debug_input == "s"

    scraper = SmartOfferScraper(min_discount=min_discount, debug=debug)

    print(f"\n[!] Iniciando busca profunda por '{query}' em até {max_pages} página(s)...")
    results = await scraper.scrape_mercadolivre(query, max_pages=max_pages)

    print("\n" + "=" * 40)
    print(f" RESULTADOS ENCONTRADOS (ORDENADOS POR DEAL SCORE): {len(results)}")
    print("=" * 40)

    if not results:
        print("Nenhuma oferta encontrada com o desconto mínimo solicitado.")
    else:
        for idx, res in enumerate(results, 1):
            print(f"\n{idx}. {res['title']}")
            print(f"   DESCONTO: {res['discount']}%")
            print(linha_terminal(res))
            print(f"   Preço: R$ {res['price']} (De R$ {res['old_price']})")
            print(f"   Parcelamento: {res['installment']}")
            print(f"   Link: {res['link']}")

    # TechDrop: se o painel pediu, salva os resultados em JSON (no terminal normal não faz nada)
    output_path = os.environ.get("TECHDROP_OUTPUT")
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n[!] Processo finalizado.")


if __name__ == "__main__":
    asyncio.run(main())