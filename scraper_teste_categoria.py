"""Scraper de TESTE (Por categoria): versao simulada de scraper_categoria.py.

Mesmas perguntas, mesmas variaveis de ambiente e mesmo JSON de saida, mas as
ofertas sao geradas (cenarios em teste_base.py). Serve para validar o Deal Score.
Uso: python scraper_teste_categoria.py   (ou iniciar_teste.bat para usar pelo painel)
"""
import asyncio

from teste_base import principal

if __name__ == "__main__":
    asyncio.run(principal("categoria"))
