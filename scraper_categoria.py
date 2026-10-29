"""
Scraper de ofertas POR CATEGORIA - Mercado Livre.

Reaproveita a classe SmartOfferScraper do scraperd.py (extração de preço,
desconto, imagem, dedupe por link, etc). Aqui só muda DE ONDE vem a lista:
em vez de uma busca por texto, o usuário escolhe uma categoria.

Duas formas de escolher a categoria:
- Terminal: menu numerado (python scraper_categoria.py)
- Painel TechDrop: o servidor define TECHDROP_CATEGORIA (+ TECHDROP_SUBCATEGORIA
  ou TECHDROP_CATEGORIA_URL) e o menu é pulado.

Coloque este arquivo na MESMA pasta do scraperd.py e do categorias_ml.py.
"""
import asyncio
import json
import logging
import os
import random
from typing import Dict, List

from playwright.async_api import async_playwright

from categorias_ml import CATEGORIAS, CUSTOM, TECNOLOGIA_SUB, montar_url
from pontuacao import linha_terminal
from scraperd import ITEMS_PER_PAGE, SmartOfferScraper

logger = logging.getLogger(__name__)

ITEM_SELECTOR = ".ui-search-layout__item, [class*='search-item']"


def _escolher(titulo: str, opcoes: List[str]) -> str:
    """Mostra um menu numerado e devolve o texto da opção escolhida."""
    print(f"\n {titulo}")
    for i, nome in enumerate(opcoes, 1):
        print(f"  {i:>2}. {nome}")
    while True:
        bruto = input(" Número: ").strip()
        if bruto.isdigit() and 1 <= int(bruto) <= len(opcoes):
            return opcoes[int(bruto) - 1]
        print(" Opção inválida, tente de novo.")


def escolher_url_categoria() -> str:
    try:
        # Painel TechDrop: a escolha já vem pronta nas variáveis de ambiente
        env_cat = os.environ.get("TECHDROP_CATEGORIA", "").strip()
        if env_cat:
            return montar_url(
                env_cat,
                os.environ.get("TECHDROP_SUBCATEGORIA", "").strip(),
                os.environ.get("TECHDROP_CATEGORIA_URL", "").strip(),
            )

        # Terminal: menu interativo
        categoria = _escolher("Escolha a categoria:", list(CATEGORIAS) + [CUSTOM])
        if categoria == CUSTOM:
            return montar_url(CUSTOM, url_custom=input(" Cole a URL da categoria: "))
        if CATEGORIAS[categoria] is None:
            sub = _escolher("Subcategoria de Tecnologia:", list(TECNOLOGIA_SUB))
            return montar_url(categoria, sub)
        return montar_url(categoria)
    except ValueError as e:
        raise SystemExit(str(e))


class CategoryOfferScraper(SmartOfferScraper):
    """Mesma extração/filtro do SmartOfferScraper, mas parte de uma URL de categoria."""

    async def scrape_category(self, base_url: str, max_pages: int = 1) -> List[Dict]:
        all_results: List[Dict] = []

        async with async_playwright() as p:
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False,
                user_agent=random.choice(self.user_agents),
                viewport={"width": 1280, "height": 720},
            )
            page = await browser_context.new_page()

            try:
                for page_num in range(1, max_pages + 1):
                    # mesma paginação do scraperd: _Desde_49, _Desde_97, ...
                    offset = (page_num - 1) * ITEMS_PER_PAGE + 1
                    url = base_url if page_num == 1 else f"{base_url}_Desde_{offset}"

                    logger.info(f"--- Página {page_num} ({url}) ---")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    except Exception as e:
                        logger.warning(f"Aviso de navegação: {e}. Tentando prosseguir...")

                    try:
                        await page.wait_for_selector(ITEM_SELECTOR, timeout=20000)
                    except Exception:
                        logger.error(
                            f"Nenhum item apareceu na página {page_num}. "
                            "Fim dos resultados ou URL de categoria inválida."
                        )
                        await self._dump_debug_html(page, f"no_items_page{page_num}")
                        break

                    # scroll gradual para carregar imagens/preços lazy-load
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await self._human_delay(2, 4)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self._human_delay(4, 6)

                    # _extract_items_on_page já aplica desconto mínimo e dedupe
                    all_results.extend(await self._extract_items_on_page(page))
                    await self._human_delay(3, 6)

                self._pontuar(all_results)

            except Exception as e:
                logger.error(f"Erro crítico no loop: {e}")
                await self._dump_debug_html(page, "critical_error")
            finally:
                await browser_context.close()

        return all_results


async def main():
    print("=" * 40)
    print(" SCRAPER DE OFERTAS POR CATEGORIA - ML ")
    print("=" * 40)

    base_url = escolher_url_categoria()
    print(f"\n Categoria: {base_url}")

    try:
        min_discount_input = input("\n Desconto mínimo desejado (ex: 10): ").strip()
        min_discount = float(min_discount_input) if min_discount_input else 0.0
    except ValueError:
        min_discount = 0.0

    try:
        max_pages = int(input(" Quantas páginas navegar? (ex: 3): ") or 1)
    except ValueError:
        max_pages = 1

    debug = input(" Salvar HTML de debug em caso de falha? (s/N): ").strip().lower() == "s"

    scraper = CategoryOfferScraper(min_discount=min_discount, debug=debug)

    print(f"\n[!] Iniciando coleta ({max_pages} página(s))...")
    results = await scraper.scrape_category(base_url, max_pages=max_pages)

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

    # mesmo contrato do scraperd: se o painel pediu, salva em JSON
    output_path = os.environ.get("TECHDROP_OUTPUT")
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n[!] Processo finalizado.")


if __name__ == "__main__":
    asyncio.run(main())
