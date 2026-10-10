"""
Scraper de ofertas por ABA da página de Ofertas - Mercado Livre.

Reaproveita a classe SmartOfferScraper do scraperd.py (preço, desconto, imagem,
dedupe, desconto mínimo). Aqui muda só como chegamos na lista: abrimos
https://www.mercadolivre.com.br/ofertas e entramos na aba escolhida.

Duas formas de escolher a aba:
- Terminal: menu numerado (python scraper_ofertas.py)
- Painel TechDrop: o servidor define TECHDROP_ABA (e TECHDROP_ABA_URL se for
  "Colar URL") e o menu é pulado.

Coloque na MESMA pasta do scraperd.py e do ofertas_abas.py.
"""
import asyncio
import json
import logging
import os
import random
import re
from typing import Dict, List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.async_api import Page, async_playwright

from ofertas_abas import ABAS, CUSTOM, OFERTAS_URL, validar_escolha
from pontuacao import linha_terminal
from scraperd import SmartOfferScraper

logger = logging.getLogger(__name__)

# Os cards da página de Ofertas usam a estrutura "poly-card" (a mesma que o
# scraperd já lê dentro da busca). Se o ML mudar o HTML, use o modo debug
# para salvar a página e ajuste só esta linha.
ITEM_SELECTOR = ".poly-card, li.promotion-item"


def _com_pagina(url: str, n: int) -> str:
    """Devolve a URL com ?page=n (a página de Ofertas pagina por parâmetro)."""
    p = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(p.query) if k != "page"] + [("page", str(n))]
    return urlunparse(p._replace(query=urlencode(query)))


def escolher_aba() -> str:
    """Devolve o nome da aba, ou a URL (se for 'Colar URL')."""
    try:
        # Painel TechDrop: escolha pronta nas variáveis de ambiente
        env_aba = os.environ.get("TECHDROP_ABA", "").strip()
        if env_aba:
            return validar_escolha(env_aba, os.environ.get("TECHDROP_ABA_URL", "").strip())

        # Terminal: menu interativo
        opcoes = ABAS + [CUSTOM]
        print("\n Escolha a aba de Ofertas:")
        for i, nome in enumerate(opcoes, 1):
            print(f"  {i:>2}. {nome}")
        while True:
            bruto = input(" Número: ").strip()
            if bruto.isdigit() and 1 <= int(bruto) <= len(opcoes):
                escolha = opcoes[int(bruto) - 1]
                break
            print(" Opção inválida, tente de novo.")
        if escolha == CUSTOM:
            return validar_escolha(CUSTOM, input(" Cole a URL da aba: "))
        return escolha
    except ValueError as e:
        raise SystemExit(str(e))


class OfertasTabScraper(SmartOfferScraper):
    """Mesma extração/filtro do SmartOfferScraper, lendo os cards da página de Ofertas."""

    ITEM_SELECTOR = ITEM_SELECTOR

    async def _abrir_aba(self, page: Page, escolha: str) -> bool:
        """Leva a página até a aba. `escolha` é o nome da aba ou uma URL completa."""
        if escolha.startswith("http"):
            await page.goto(escolha, wait_until="domcontentloaded", timeout=45000)
            return True

        await page.goto(OFERTAS_URL, wait_until="domcontentloaded", timeout=45000)
        if escolha == ABAS[0]:
            return True  # "Todas as ofertas" já é a página principal

        # As abas NÃO são links (<a>): são <div role="button"> de um carrossel, sem href.
        # Mas a página traz, embutido no HTML, o filtro de cada aba, por exemplo:
        #   "name":"Ofertas relâmpago","filter":{"promotion_type":"lightning","container_id":"MLB779362-1"}
        # Lemos esse filtro e montamos a URL: /ofertas?promotion_type=lightning&container_id=...
        html = await page.content()
        filtro = self._filtro_da_aba(html, escolha)
        if filtro is not None:
            url = f"{OFERTAS_URL}?{urlencode(filtro)}"
            logger.info(f"Filtro da aba '{escolha}': {filtro}")
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            return True

        # Plano B: clica no botão da aba pelo texto (<p class="title">)
        logger.warning("Filtro da aba não encontrado no HTML; tentando clicar na aba.")
        botao = page.locator(".carousel_item", has=page.locator("p.title", has_text=re.compile(rf"^\s*{re.escape(escolha)}\s*$", re.I))).first
        try:
            await botao.wait_for(state="attached", timeout=15000)
            await botao.scroll_into_view_if_needed(timeout=5000)
            await botao.click(timeout=10000)
            await page.wait_for_load_state("domcontentloaded")
            await self._human_delay(2, 3)
            return True
        except Exception:
            logger.error(
                f"Não achei a aba '{escolha}' na página de Ofertas. "
                "Confira o nome ou use 'Colar URL'."
            )
            await self._dump_debug_html(page, "aba_nao_encontrada")
            return False

    @staticmethod
    def _filtro_da_aba(html: str, nome: str):
        """Procura no HTML o filtro (dict) da aba com esse nome. None se não achar."""
        for m in re.finditer(r'"name":"([^"]+)","filter":(\{[^}]*\})', html):
            try:
                if json.loads(f'"{m.group(1)}"').strip().lower() == nome.strip().lower():
                    return json.loads(m.group(2))
            except ValueError:
                continue
        return None

    async def scrape_aba(self, escolha: str, max_pages: int = 1) -> List[Dict]:
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
                logger.info(f"--- Abrindo aba: {escolha} ---")
                if not await self._abrir_aba(page, escolha):
                    return all_results
                base_url = page.url
                logger.info(f"Aba aberta em {base_url}")

                for page_num in range(1, max_pages + 1):
                    if page_num > 1:
                        url = _com_pagina(base_url, page_num)
                        logger.info(f"--- Página {page_num} ({url}) ---")
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        except Exception as e:
                            logger.warning(f"Aviso de navegação: {e}. Tentando prosseguir...")
                    else:
                        logger.info("--- Página 1 ---")

                    try:
                        await page.wait_for_selector(ITEM_SELECTOR, timeout=20000)
                    except Exception:
                        logger.error(
                            f"Nenhum item apareceu na página {page_num}. "
                            "Fim dos resultados ou o HTML da página mudou."
                        )
                        await self._dump_debug_html(page, f"no_items_page{page_num}")
                        break

                    # scroll gradual para carregar imagens/preços lazy-load
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await self._human_delay(1, 2)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self._human_delay(2, 3)

                    # _extract_items_on_page já aplica desconto mínimo e dedupe
                    all_results.extend(await self._extract_items_on_page(page))
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
    print(" SCRAPER DE OFERTAS POR ABA - ML ")
    print("=" * 40)

    escolha = escolher_aba()
    print(f"\n Aba: {escolha}")

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

    scraper = OfertasTabScraper(min_discount=min_discount, debug=debug)

    print(f"\n[!] Iniciando coleta ({max_pages} página(s))...")
    results = await scraper.scrape_aba(escolha, max_pages=max_pages)

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
