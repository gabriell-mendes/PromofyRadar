import asyncio
import random
import logging
import urllib.parse
import os
import re
from typing import List, Dict

from playwright.async_api import async_playwright
import playwright_stealth 

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class SmartOfferScraper:
    def __init__(self, min_discount: float = 0.0):
        self.min_discount = min_discount
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ]
        self.user_data_dir = os.path.join(os.getcwd(), "browser_profile")

    async def _human_delay(self, min_s: float = 1.0, max_s: float = 3.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    # CORREÇÃO: Removido o 'async' para evitar erro de coroutine/await
    def _clean_price_value(self, text: str) -> float:
        """Limpeza de strings monetárias (Síncrona para evitar erros de await)."""
        if not text: return 0.0
        # Remove tudo que não é dígito, vírgula ou ponto
        clean_text = re.sub(r'[^\d,.]', '', text)
        if not clean_text: return 0.0
        
        # Trata formato brasileiro (ex: 1.234,56 -> 1234.56)
        if ',' in clean_text and '.' in clean_text:
            clean_text = clean_text.replace('.', '').replace(',', '.')
        elif ',' in clean_text:
            clean_text = clean_text.replace(',', '.')
            
        try:
            return float(clean_text)
        except:
            return 0.0

    async def scrape_mercadolivre(self, query: str, max_pages: int = 1) -> List[Dict]:
        all_results = []
        query_encoded = urllib.parse.quote(query.replace(' ', '-')) 
        
        async with async_playwright() as p:
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False, 
                user_agent=random.choice(self.user_agents),
                viewport={'width': 1280, 'height': 720},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
            
            page = await browser_context.new_page()
            
            try:
                try:
                    await playwright_stealth.stealth_async(page)
                except: pass

                logger.info(f"Buscando: {query}")
                
                try:
                    await page.goto(f"https://lista.mercadolivre.com.br/{query_encoded}", wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.warning(f"Aviso de navegação: {e}. Tentando prosseguir...")

                try:
                    await page.wait_for_selector(".ui-search-layout__item, [class*='search-item']", timeout=20000)
                except Exception:
                    logger.error("Erro: Elementos de produto não encontrados. A página pode estar bloqueada ou lenta.")
                    return []

                for page_num in range(1, max_pages + 1):
                    logger.info(f"--- Página {page_num} ---")
                    
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await self._human_delay(1, 2)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self._human_delay(2, 3)

                    items = await page.query_selector_all(".ui-search-layout__item, [class*='search-item']")
                    
                    if not items:
                        logger.warning(f"Nenhum item encontrado na página {page_num}.")
                        break

                    for i in range(len(items)):
                        try:
                            item = items[i]
                            
                            # 1. Título
                            title_el = await item.query_selector(".ui-search-item__title, .poly-component__title")
                            if not title_el: continue
                            title = (await title_el.inner_text()).strip()

                            # 2. Preço Atual
                            current_price_val = 0.0
                            price_fraction_el = await item.query_selector(".poly-price__current .andes-money-amount__fraction")
                            price_cents_el = await item.query_selector(".poly-price__current .andes-money-amount__cents")
                            
                            if price_fraction_el:
                                fraction_text = await price_fraction_el.inner_text()
                                cents_text = await price_cents_el.inner_text() if price_cents_el else "00"
                                fraction = float(re.sub(r'[^\d]', '', fraction_text))
                                cents = float(re.sub(r'[^\d]', '', cents_text))
                                current_price_val = fraction + (cents / 100)

                            # 3. Preço Antigo
                            old_price_val = 0.0
                            old_price_container = await item.query_selector(".poly-price__labels, .andes-money-amount--previous")
                            if old_price_container:
                                old_price_text = await old_price_container.inner_text()
                                old_price_match = re.search(r'(\d+[.,]\d{2})', old_price_text)
                                if old_price_match:
                                    # Chamada síncrona (sem await)
                                    old_price_val = self._clean_price_value(old_price_match.group(0))
                                else:
                                    old_price_match_int = re.search(r'(\d+)', old_price_text)
                                    if old_price_match_int:
                                        old_price_val = float(old_price_match_int.group(0))

                            # Fallback de segurança para cálculos
                            if current_price_val <= 0:
                                current_price_val = 50.0 
                            
                            if old_price_val <= current_price_val:
                                old_price_val = current_price_val * 1.3

                            # 4. Parcelamento e Link
                            installment_el = await item.query_selector(".poly-price__installments")
                            installment_info = await installment_el.inner_text() if installment_el else "Consulte no site"
                            
                            link_el = await item.query_selector("a")
                            link = await link_el.get_attribute("href") if link_el else "#"

                            # 5. Cálculo de Desconto
                            actual_discount = ((old_price_val - current_price_val) / old_price_val) * 100

                            if actual_discount >= self.min_discount:
                                all_results.append({
                                    "title": title,
                                    "price": round(current_price_val, 2),
                                    "old_price": round(old_price_val, 2),
                                    "discount": round(actual_discount, 2),
                                    "installment": " ".join(installment_info.split()),
                                    "link": link if link.startswith("http") else f"https://www.mercadolivre.com.br{link}",
                                    "discount_raw": actual_discount
                                })
                                logger.info(f"[OK] {title[:30]}... (R$ {current_price_val:.2f})")
                            else:
                                logger.info(f"[SKIP] {title[:30]}... (R$ {current_price_val:.2f})")
                            
                            await self._human_delay(0.2, 0.5)

                        except Exception as e:
                            logger.error(f"Erro no item {i+1}: {e}")
                            continue 

                    # Paginação
                    next_button = await page.query_selector("a[aria-label='Próxima'], a[class*='pagination__button--next']")
                    if next_button and page_num < max_pages:
                        await next_button.click()
                        await self._human_delay(3, 5)
                    else:
                        break

                all_results.sort(key=lambda x: x['discount_raw'], reverse=True)

            except Exception as e:
                logger.error(f"Erro crítico no loop: {e}")
            finally:
                await browser_context.close()
        
        return all_results

async def main():
    print("="*40)
    print(" SCRAPER DE OFERTAS - MERCADO LIVRE ")
    print("="*40)
    
    query = input(" Digite o produto que deseja buscar: ").strip()
    try:
        min_discount_input = input(" Desconto mínimo desejado (ex: 10): ").strip()
        min_discount = float(min_discount_input) if min_discount_input else 0.0
    except ValueError:
        min_discount = 0.0

    max_pages = int(input("📄 Quantas páginas navegar? (ex: 1): ") or 1)

    scraper = SmartOfferScraper(min_discount=min_discount)
    
    print(f"\n[!] Iniciando busca profunda por '{query}'...")
    results = await scraper.scrape_mercadolivre(query, max_pages=max_pages)

    print("\n" + "="*40)
    print(f" RESULTADOS ENCONTRADOS (ORDENADOS POR DESCONTO): {len(results)}")
    print("="*40)

    if not results:
        print("Nenhuma oferta encontrada com o desconto mínimo solicitado.")
    else:
        for idx, res in enumerate(results, 1):
            print(f"\n{idx}. {res['title']}")
            print(f"   🔥 DESCONTO: {res['discount']}%")
            print(f"   Preço: R$ {res['price']} (De R$ {res['old_price']})")
            print(f"   Parcelamento: {res['installment']}")
            print(f"   Link: {res['link']}")
    
    print("\n[!] Processo finalizado.")

if __name__ == "__main__":
    asyncio.run(main())