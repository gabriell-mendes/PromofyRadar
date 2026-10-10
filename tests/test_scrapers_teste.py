"""Valida o Deal Score ponta a ponta com os scrapers de teste (sem navegador)."""
import asyncio
from datetime import date

import pytest

from historico import chave_produto, obter
from teste_base import FakeOfferScraper

HOJE = date(2026, 9, 30)


def _rodar(tmp_path, tipo="busca", tema="ssd", min_discount=0.0, max_pages=2, nome_db="h.db"):
    scraper = FakeOfferScraper(min_discount=min_discount, hoje=HOJE, db=tmp_path / nome_db)
    return asyncio.run(scraper.scrape(tipo, tema, max_pages=max_pages))


def _por_nome(resultados, trecho):
    achados = [o for o in resultados if trecho in o["title"]]
    assert len(achados) == 1, f"esperava 1 oferta com '{trecho}', achei {len(achados)}"
    return achados[0]


def test_mesma_logica_de_filtro_do_scraper_real(tmp_path):
    r = _rodar(tmp_path)
    titulos = " | ".join(o["title"] for o in r)
    assert "Sem preço legível" not in titulos          # preco 0 e pulado
    assert "Duplicado" not in titulos                  # link repetido e pulado
    assert len(r) == 10
    assert all(o["teste"] is True for o in r)
    assert all({"title", "price", "old_price", "discount", "installment", "link", "image"} <= o.keys() for o in r)


def test_toda_oferta_sai_com_campos_do_deal_score(tmp_path):
    for o in _rodar(tmp_path):
        assert {"deal_score", "deal_confianca", "deal_motivos", "deal_flags"} <= o.keys()


def test_ordenado_do_maior_para_o_menor_score(tmp_path):
    scores = [o["deal_score"] for o in _rodar(tmp_path)]
    assert scores == sorted(scores, reverse=True)


def test_otimo_negocio_lidera_com_confianca_alta(tmp_path):
    r = _rodar(tmp_path)
    assert r[0]["title"].endswith("Ótimo negócio real")
    assert r[0]["deal_score"] >= 90
    assert r[0]["deal_confianca"] == "alta"
    assert "menor_preco_recente" in r[0]["deal_flags"]


def test_falso_desconto_tem_nota_baixa_apesar_do_desconto_anunciado(tmp_path):
    falso = _por_nome(_rodar(tmp_path), "Falso desconto")
    assert falso["discount"] > 35                      # a loja anuncia quase 40% off
    assert falso["deal_score"] <= 10                   # mas o score nao cai nessa
    assert "desconto_inflado" in falso["deal_flags"]


def test_desconto_real_sem_preco_anunciado_ainda_pontua(tmp_path):
    p = _por_nome(_rodar(tmp_path), "Desconto real sem anúncio")
    assert p["discount"] == 0
    assert p["deal_score"] >= 40


def test_preco_subiu_e_precos_normais_ficam_perto_de_zero(tmp_path):
    r = _rodar(tmp_path)
    for trecho in ("Preço subiu", "Preço normal A", "Preço normal B", "Preço normal C"):
        assert _por_nome(r, trecho)["deal_score"] <= 5, trecho


def test_produto_novo_tem_confianca_baixa(tmp_path):
    r = _rodar(tmp_path)
    assert _por_nome(r, "Produto novo barato")["deal_confianca"] == "baixa"
    assert _por_nome(r, "Produto novo caro")["deal_confianca"] == "baixa"
    assert _por_nome(r, "Produto novo caro")["deal_score"] == 0


def test_filtro_de_desconto_minimo_nao_muda_a_nota(tmp_path):
    """O grupo e formado por TODOS os itens vistos, nao so pelos que passaram no filtro."""
    tudo = _rodar(tmp_path, nome_db="a.db")
    filtrado = _rodar(tmp_path, min_discount=10, nome_db="b.db")
    assert len(filtrado) < len(tudo)
    for o in filtrado:
        assert o["deal_score"] == _por_nome(tudo, o["title"])["deal_score"]


def test_rodar_duas_vezes_no_mesmo_dia_da_o_mesmo_resultado(tmp_path):
    a = [(o["title"], o["deal_score"]) for o in _rodar(tmp_path)]
    b = [(o["title"], o["deal_score"]) for o in _rodar(tmp_path)]
    assert a == b


def test_precos_de_hoje_entram_no_historico_depois_da_nota(tmp_path):
    r = _rodar(tmp_path)
    otimo = _por_nome(r, "Ótimo negócio real")
    chave = chave_produto(otimo["link"])
    db = tmp_path / "h.db"
    ontem_para_tras = obter([chave], antes_de=HOJE, db=db)[chave]
    assert len(ontem_para_tras) == 14                          # a nota usou so os 14 dias anteriores
    com_hoje = obter([chave], antes_de=date(2026, 10, 1), db=db)[chave]
    assert com_hoje[-1] == 210.0                               # e o preco de hoje foi gravado


def test_sem_historico_so_grupo_vale(tmp_path, monkeypatch):
    monkeypatch.setenv("TECHDROP_TESTE_SEM_HISTORICO", "1")
    r = _rodar(tmp_path)
    assert {o["deal_confianca"] for o in r} == {"baixa"}


@pytest.mark.parametrize("tipo,tema", [("categoria", "Informática"), ("ofertas", "Ofertas relâmpago")])
def test_categoria_e_ofertas_usam_o_mesmo_motor(tmp_path, tipo, tema):
    r = _rodar(tmp_path, tipo=tipo, tema=tema)
    assert len(r) == 10
    assert r[0]["title"].endswith("Ótimo negócio real")
    assert all(f"/{tipo}/" in o["link"] for o in r)


def test_historicos_de_temas_diferentes_nao_se_misturam(tmp_path):
    a = _rodar(tmp_path, tema="ssd")
    b = _rodar(tmp_path, tema="notebook")
    assert {o["link"] for o in a}.isdisjoint({o["link"] for o in b})
