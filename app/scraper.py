"""OBSOLETO — substituído por app/sources/mercadolivre_scraper.py.

Este arquivo era um rascunho de aprendizado (Playwright + asyncio) que
ainda devolvia dados MOCADOS (veja o comentário antigo "Simulando extração
de dados para fins de exemplo de estrutura") e não passava pela interface
OfferSource nem virava Product. Cumpriu o papel de validar que a estrutura
básica de scraping assíncrono funcionava.

A partir de 2026-09-16, a extração real do Mercado Livre (seletores de
verdade, limpeza de preço, integração com Product/scoring/dashboard) vive
em app/sources/mercadolivre_scraper.py, implementando OfferSource.

Pode apagar este arquivo com segurança:

    Remove-Item app\\scraper.py
"""
