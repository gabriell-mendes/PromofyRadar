import asyncio
import random
import logging
import urllib.parse  # <--- IMPORTANTE para tratar a URL
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional

from playwright.async_api import async_playwright, Page
from playwright_stealth import stealth_sync as stealth_async

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class SmartOfferScraper:
    def __init__(self, min_discount: float = 30.0):
        self.min_discount = min_discount
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]

    async def _human_delay(self, min_s: float = 1.0, max_s: float = 3.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _setup_stealth_page(self, context, url: str) -> Page:
        page = await context.new_page()
        await stealth_async(page)
        await page.set_viewport_size({"width": 1280, "height": 720})
        
        logger.info(f"Navegando para: {url}")
        # Aumentamos o timeout para garantir que a página carregue
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        return page

    async def scrape_mercadolivre(self, query: str, limit: int = 5) -> List[Dict]:
        results = []
        
        # --- LÓGICA DE URL MELHORADA ---
        # Em vez de apenas substituir espaços por hífens, vamos usar o padrão de busca real
        # que você encontrou, garantindo que a URL seja válida.
        query_encoded = urllib.parse.quote(query) # Converte "caixa de som" para "caixa%20de%20som"
        search_url = f"https://lista.mercadolivre.com.br/{query_encoded}#D[A:{query_encoded}]"
        # -------------------------------

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False) # Mantenha False para depurar
            context = await browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={'width': 1280, 'height': 720}
            )
            
            page = await self._setup_stealth_page(context, search_url)
            
            try:
                # Espera um seletor genérico para garantir que a página não está vazia
                # Vamos esperar pelo menos 5 segundos ou até um elemento aparecer
                await page.wait_for_timeout(5000) 

                # Verifica se houve erro de busca (ex: página de erro ou busca vazia)
                if "Nenhum resultado encontrado" in await page.content():
                    logger.warning(f"Busca para '{query}' retornou zero resultados no ML.")
                    return []

                # Tenta encontrar os itens (usando o seletor que você já tem)
                # Se o seletor mudar, o erro será capturado pelo try/except
                await page.wait_for_selector(".ui-search-layout__item", timeout=10000)
                
                # Scroll para carregar conteúdo dinâmico
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await self._human_delay(1, 2)

                items = await page.query_selector_all(".ui-search-layout__item")
                logger.info(f"Encontrados {len(items)} itens. Analisando...")

                for i in range(min(len(items), limit)):
                    item = items[i]
                    
                    # Extração de dados
                    title_el = await item.query_selector(".ui-search-item__title")
                    price_el = await item.query_selector(".andes-money-amount__fraction")
                    link_el = await item.query_selector("a")

                    if title_el and price_el:
                        title = await title_el.inner_text()
                        price_raw = await price_el.inner_text()
                        link = await link_el.get_attribute("href") if link_el else "#"

                        # Limpeza de preço
                        try:
                            price_val = float(price_raw.replace('.', '').replace(',', '.'))
                        except ValueError:
                            continue

                        # Simulação de desconto para teste (Como você está em fase de testes)
                        simulated_old_price = price_val * 1.4 
                        discount = ((simulated_old_price - price_val) / simulated_old_price) * 100

                        if discount >= self.min_discount:
                            results.append({
                                "platform": "Mercado Livre",
                                "title": title.strip(),
                                "price": price_val,
                                "old_price": round(simulated_old_price, 2),
                                "discount": round(discount, 2),
                                "link": link if link.startswith("http") else f"https://www.mercadolivre.com.br{link}"
                            })
                            logger.info(f"[OK] {title[:30]}... ({discount:.0f}% OFF)")
                        
                        await self._human_delay(0.5, 1.5)
                    
                    if len(results) >= limit: break

            except Exception as e:
                logger.error(f"Erro durante a raspagem: {e}")
            finally:
                await browser.close()
        
        return results

# --- CLI (Mantida igual) ---
async def main():
    print("="*40)
    print(" SMART OFFER SCRAPER - MODO MANUAL")
    print("="*40)
    
    query = input("🔍 Digite o produto que deseja buscar: ").strip()
    try:
        min_discount = float(input("📉 Desconto mínimo desejado (ex: 30): "))
    except ValueError:
        print(" Erro: Digite um número válido.")
        return

    scraper = SmartOfferScraper(min_discount=min_discount)
    
    print(f"\n[!] Iniciando busca por '{query}'...")
    results = await scraper.scrape_mercadolivre(query, limit=5)

    print("\n" + "="*40)
    print(f" RESULTADOS ENCONTRADOS: {len(results)}")
    print("="*40)

    if not results:
        print("Nenhuma oferta encontrada com os critérios informados.")
    else:
        for idx, res in enumerate(results, 1):
            print(f"\n{idx}. {res['title']}")
            print(f"   Preço: R$ {res['price']} (De R$ {res['old_price']})")
            print(f"   Desconto: {res['discount']}%")
            print(f"   Link: {res['link']}")
    
    print("\n[!] Processo finalizado.")

if __name__ == "__main__":
    asyncio.run(main())