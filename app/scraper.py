import asyncio
import random
from typing import List, Dict
from playwright.async_api import async_playwright

class OfferScraper:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ]

    async def _get_browser_context(self, browser):
        """Configura o contexto do navegador com um User-Agent aleatório."""
        context = await browser.new_context(
            user_agent=random.choice(self.user_agents),
            viewport={'width': 1280, 'height': 720}
        )
        return context

    async def scrape_mercadolivre(self, query: str) -> List[Dict]:
        """Scraper para Mercado Livre focado em encontrar descontos > 30%."""
        print(f"[!] Iniciando busca no Mercado Livre: {query}")
        results = []
        
        # URL de busca (exemplo simplificado)
        url = f"https://lista.mercadolivre.com.br/{query.replace(' ', '-')}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await self._get_browser_context(browser)
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                # Aqui entraria a lógica de extração de elementos
                # Simulando extração de dados para fins de exemplo de estrutura
                # Em um cenário real, você buscaria o seletor do preço original e preço atual
                
                # Exemplo de lógica de validação de desconto:
                # preco_original = float(elemento.get_text())
                # preco_atual = float(elemento.get_text())
                # desconto = ((preco_original - preco_atual) / preco_original) * 100
                
                # Mock de dado para demonstração da estrutura de retorno
                results.append({
                    "platform": "Mercado Livre",
                    "product": f"{query} - Exemplo de Produto",
                    "price": 700.00,
                    "discount": 35.0, # %
                    "link": f"https://www.mercadolivre.com.br/p/{random.randint(100,999)}"
                })
                
            except Exception as e:
                print(f"[X] Erro no Mercado Livre: {e}")
            finally:
                await browser.close()
        
        return results

    async def scrape_shopee(self, query: str) -> List[Dict]:
        """Scraper para Shopee."""
        print(f"[!] Iniciando busca na Shopee: {query}")
        results = []
        
        url = f"https://shopee.com.br/search?keyword={query}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await self._get_browser_context(browser)
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until="domcontentloaded")
                # A Shopee tem carregamento pesado de JS, pode ser necessário scroll
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(5) # Espera o carregamento dinâmico
                
                # Lógica de extração simulada
                results.append({
                    "platform": "Shopee",
                    "product": f"{query} - Oferta Imperdível",
                    "price": 150.00,
                    "discount": 40.0,
                    "link": f"https://shopee.com.br/product/{random.randint(1,1000)}"
                })
            except Exception as e:
                print(f"[X] Erro na Shopee: {e}")
            finally:
                await browser.close()
                
        return results

    async def run_search(self, query: str) -> List[Dict]:
        """Método principal para orquestrar a busca em ambas as plataformas."""
        print(f"\n--- Buscando Ofertas para: {query.upper()} ---")
        
        # Executa as buscas em paralelo para ganhar eficiência
        tasks = [
            self.scrape_mercadolivre(query),
            self.scrape_shopee(query)
        ]
        
        all_results = await asyncio.gather(*tasks)
        
        # Achata a lista de listas e filtra por desconto mínimo (30%)
        flattened_results = [item for sublist in all_results for item in sublist]
        valid_offers = [
            offer for offer in flattened_results 
            if offer['discount'] >= 30
        ]
        
        return valid_offers

# --- Exemplo de Uso ---
async def main():
    scraper = OfferScraper()
    
    # Lista de termos de busca que você quer testar
    termos_de_busca = ["notebook", "camisa", "mouse"]
    
    for termo in termos_de_busca:
        ofertas = await scraper.run_search(termo)
        
        print(f"\n[RESULTADO] Encontradas {len(ofertas)} ofertas com > 30% de desconto:")
        for oferta in ofertas:
            print(f"- [{oferta['platform']}] {oferta['product']}")
            print(f"  Preço: R$ {oferta['price']} | Desconto: {oferta['discount']}%")
            print(f"  Link: {oferta['link']}\n")
        
        # Respeitando o Rate Limit de 3 minutos (180 segundos)
        # No modo de produção, você pode diminuir para testes, mas para o real:
        print("[...] Aguardando 3 minutos para a próxima busca para evitar banimento...")
        await asyncio.sleep(180) 

if __name__ == "__main__":
    asyncio.run(main())