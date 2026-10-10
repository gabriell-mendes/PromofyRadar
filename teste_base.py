"""Base dos scrapers de TESTE do Deal Score.

Mesmo contrato dos scrapers reais (scraperd.py, scraper_categoria.py,
scraper_ofertas.py), mas sem navegador: em vez de ler o HTML do Mercado Livre,
geram ofertas sinteticas de cenarios conhecidos. Assim da para conferir se a
nota sai como esperada sem depender do site.

O que e IGUAL ao scraper real:
- as mesmas perguntas no terminal, na mesma ordem (o painel responde sozinho)
- as mesmas variaveis de ambiente (TECHDROP_CATEGORIA, TECHDROP_ABA, ...)
- a mesma saida em JSON (TECHDROP_OUTPUT) e os mesmos campos por oferta
- a mesma filtragem: pula preco invalido, deduplica por link, calcula o
  desconto anunciado, corta pelo desconto minimo, guarda TODOS os itens vistos
  para o grupo do Deal Score, pagina de N em N itens
- a mesma pontuacao (pontuacao.pontuar_e_ordenar)

O que e DIFERENTE, de proposito:
- o historico vai para data/historico_teste.db, nunca para o historico real
- antes de pontuar, semeia 14 dias de historico sintetico (idempotente)
- os links usam teste.techdrop.local e as ofertas saem com "teste": true

Para rodar os cenarios sem historico (produto novo em tudo), defina
TECHDROP_TESTE_SEM_HISTORICO=1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

from categorias_ml import CATEGORIAS, CUSTOM, TECNOLOGIA_SUB, montar_url
from historico import chave_produto, registrar
from ofertas_abas import ABAS, CUSTOM as CUSTOM_ABA, validar_escolha
from pontuacao import linha_terminal, pontuar_e_ordenar

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DB_TESTE = Path(os.environ.get("TECHDROP_HISTORICO_TESTE_DB") or Path(__file__).resolve().parent / "data" / "historico_teste.db")
ITEMS_PER_PAGE = 6
DIAS_HISTORICO = 14

# nome, preco hoje, preco "de" anunciado (None = sem desconto anunciado),
# preco base do historico (None = produto novo, sem historico), o que esperamos
CENARIOS = [
    ("Ótimo negócio real", 210, 300, 300, "score alto, menor preço recente"),
    ("Bom desconto real", 272, 320, 320, "score médio, confiança alta"),
    ("Falso desconto", 290, 480, 290, "score perto de 0, flag desconto_inflado"),
    ("Preço subiu", 330, 350, 280, "score 0"),
    ("Preço normal A", 300, None, 300, "score perto de 0"),
    ("Preço normal B", 310, 320, 310, "score perto de 0"),
    ("Preço normal C", 295, None, 295, "score perto de 0"),
    ("Desconto real sem anúncio", 264, None, 330, "score bom mesmo sem 'de' anunciado"),
    ("Produto novo barato", 230, 260, None, "confiança baixa, nota só pelo grupo"),
    ("Produto novo caro", 340, None, None, "confiança baixa, score 0"),
    ("Sem preço legível", 0, None, None, "descartado pelo scraper, como no real"),
    ("Duplicado do Ótimo", 210, 300, None, "descartado pelo dedupe de link"),
]


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "x"


def gerar_linhas(tipo: str, tema: str) -> List[Dict]:
    """Itens 'crus', como o scraper real leria do HTML (antes de qualquer filtro)."""
    linhas = []
    for nome, preco, de, _base, esperado in CENARIOS:
        slug_nome = "otimo-negocio-real" if nome.startswith("Duplicado") else _slug(nome)
        linhas.append({
            "title": f"[TESTE] {tema} - {nome}",
            "price": float(preco),
            "old_price": float(de) if de else 0.0,
            "link": f"https://teste.techdrop.local/{tipo}/{_slug(tema)}/{slug_nome}?pdp_filters=deal%3ATESTE",
            "image": "",
            "installment": f"Esperado: {esperado}",
        })
    return linhas


def semear_historico(tipo: str, tema: str, hoje: date, db=DB_TESTE) -> int:
    """Grava DIAS_HISTORICO dias de preco por produto (base +-2%), nos dias ANTES de hoje."""
    total = 0
    for nome, _preco, _de, base, _esp in CENARIOS:
        if base is None or nome.startswith("Duplicado"):
            continue
        chave = chave_produto(f"https://teste.techdrop.local/{tipo}/{_slug(tema)}/{_slug(nome)}")
        for d in range(1, DIAS_HISTORICO + 1):
            dia = hoje - timedelta(days=d)
            ruido = random.Random(f"{chave}{dia}").uniform(-0.02, 0.02)
            total += registrar([(chave, round(base * (1 + ruido), 2))], quando=dia, db=db)
    return total


class FakeOfferScraper:
    """Mesma interface e mesma logica de filtro do SmartOfferScraper, sem navegador."""

    def __init__(self, min_discount: float = 0.0, debug: bool = False, hoje: date | None = None, db=DB_TESTE):
        self.min_discount = min_discount
        self.debug = debug
        self.hoje = hoje or date.today()
        self.db = db
        self.seen_links = set()
        self.todos_vistos: List[Dict] = []

    def _extract_items_on_page(self, linhas: List[Dict]) -> List[Dict]:
        page_results: List[Dict] = []
        for item in linhas:
            title, link = item["title"], item["link"]
            current_price_val = item["price"]
            old_price_val = item["old_price"]

            if not link or link in self.seen_links:
                continue
            if current_price_val <= 0:
                logger.warning(f"[SKIP-NOPRICE] {title[:40]}...")
                continue

            if old_price_val <= 0 or old_price_val <= current_price_val:
                old_price_val = current_price_val
                actual_discount = 0.0
            else:
                actual_discount = ((old_price_val - current_price_val) / old_price_val) * 100

            self.seen_links.add(link)
            self.todos_vistos.append({"link": link, "price": round(current_price_val, 2)})

            if actual_discount >= self.min_discount:
                page_results.append({
                    "title": title,
                    "price": round(current_price_val, 2),
                    "old_price": round(old_price_val, 2),
                    "discount": round(actual_discount, 2),
                    "installment": item["installment"],
                    "link": link,
                    "image": item["image"],
                    "teste": True,
                })
                logger.info(f"[OK] {title[:30]}... (R$ {current_price_val:.2f}, {actual_discount:.1f}% off)")
            else:
                logger.info(f"[SKIP] {title[:30]}... ({actual_discount:.1f}% off < mínimo)")
        return page_results

    async def scrape(self, tipo: str, tema: str, max_pages: int = 1) -> List[Dict]:
        linhas = gerar_linhas(tipo, tema)
        if not os.environ.get("TECHDROP_TESTE_SEM_HISTORICO"):
            n = semear_historico(tipo, tema, self.hoje, self.db)
            logger.info(f"Histórico sintético pronto ({n} registros, {DIAS_HISTORICO} dias) em {Path(self.db).name}")

        all_results: List[Dict] = []
        for page_num in range(1, max_pages + 1):
            fatia = linhas[(page_num - 1) * ITEMS_PER_PAGE: page_num * ITEMS_PER_PAGE]
            logger.info(f"--- Página {page_num} (simulada) ---")
            if not fatia:
                logger.error(f"Nenhum item apareceu na página {page_num}. Provavelmente é o fim dos resultados.")
                break
            all_results.extend(self._extract_items_on_page(fatia))

        return pontuar_e_ordenar(all_results, self.todos_vistos, hoje=self.hoje, db=self.db)


# ---------- CLI, espelhando as perguntas dos scrapers reais ----------

def _escolher(titulo: str, opcoes: List[str]) -> str:
    print(f"\n {titulo}")
    for i, nome in enumerate(opcoes, 1):
        print(f"  {i:>2}. {nome}")
    while True:
        bruto = input(" Número: ").strip()
        if bruto.isdigit() and 1 <= int(bruto) <= len(opcoes):
            return opcoes[int(bruto) - 1]
        print(" Opção inválida, tente de novo.")


def _tema_categoria() -> str:
    try:
        env_cat = os.environ.get("TECHDROP_CATEGORIA", "").strip()
        if env_cat:
            montar_url(env_cat, os.environ.get("TECHDROP_SUBCATEGORIA", "").strip(),
                       os.environ.get("TECHDROP_CATEGORIA_URL", "").strip())
            return os.environ.get("TECHDROP_SUBCATEGORIA", "").strip() or env_cat
        categoria = _escolher("Escolha a categoria:", list(CATEGORIAS) + [CUSTOM])
        if categoria == CUSTOM:
            return montar_url(CUSTOM, url_custom=input(" Cole a URL da categoria: ")).rsplit("/", 1)[-1]
        if CATEGORIAS[categoria] is None:
            return _escolher("Subcategoria de Tecnologia:", list(TECNOLOGIA_SUB))
        return categoria
    except ValueError as e:
        raise SystemExit(str(e))


def _tema_aba() -> str:
    try:
        env_aba = os.environ.get("TECHDROP_ABA", "").strip()
        if env_aba:
            return validar_escolha(env_aba, os.environ.get("TECHDROP_ABA_URL", "").strip())
        escolha = _escolher("Escolha a aba de Ofertas:", ABAS + [CUSTOM_ABA])
        if escolha == CUSTOM_ABA:
            return validar_escolha(CUSTOM_ABA, input(" Cole a URL da aba: "))
        return escolha
    except ValueError as e:
        raise SystemExit(str(e))


async def principal(tipo: str) -> None:
    """Fluxo completo do scraper de teste. tipo: 'busca', 'categoria' ou 'ofertas'."""
    titulos = {"busca": "BUSCA", "categoria": "CATEGORIA", "ofertas": "ABA DE OFERTAS"}
    print("=" * 40)
    print(f" SCRAPER DE TESTE ({titulos[tipo]}) - DEAL SCORE ")
    print("=" * 40)

    if tipo == "busca":
        tema = input(" Digite o produto que deseja buscar: ").strip() or "produto"
    elif tipo == "categoria":
        tema = _tema_categoria()
        print(f"\n Categoria: {tema}")
    else:
        tema = _tema_aba()
        print(f"\n Aba: {tema}")

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

    scraper = FakeOfferScraper(min_discount=min_discount, debug=debug)
    print(f"\n[!] Iniciando coleta SIMULADA ({max_pages} página(s))...")
    results = await scraper.scrape(tipo, tema, max_pages=max_pages)

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
            for motivo in res.get("deal_motivos", []):
                print(f"     - {motivo}")
            print(f"   Preço: R$ {res['price']} (De R$ {res['old_price']})")
            print(f"   {res['installment']}")
            print(f"   Link: {res['link']}")

    output_path = os.environ.get("TECHDROP_OUTPUT")
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n[!] Processo finalizado.")
