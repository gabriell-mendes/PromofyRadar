"""Testes do comportamento comum a QUALQUER fonte (app/sources/base.py):
descarte de item inválido/incompleto e deduplicação. Usa uma fonte falsa
mínima em vez de uma fonte real, porque isso é lógica da base, não de uma
fonte específica.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.models import Product
from app.sources.base import OfferSource


class FonteFalsa(OfferSource):
    name = "falsa"

    def __init__(self, itens_crus):
        self._itens_crus = itens_crus

    def buscar_produtos_raw(self, query, limit=20):
        return self._itens_crus

    def normalizar(self, item_cru):
        if "id" not in item_cru:
            raise ValueError("sem id")
        preco = item_cru.get("price")
        if preco is None or preco <= 0:
            raise ValueError("sem preço válido")
        return Product(
            source=self.name,
            source_id=str(item_cru["id"]),
            title=item_cru.get("title", "(sem título)"),
            price=Decimal(str(preco)),
            url=item_cru.get("url", "https://exemplo.com"),
            store="Loja teste",
            collected_at=datetime(2026, 1, 1),
        )


def test_resposta_vazia_nao_quebra():
    fonte = FonteFalsa([])
    assert fonte.buscar_produtos("q") == []


def test_produto_sem_preco_e_descartado_sem_derrubar_os_outros():
    itens = [
        {"id": "1", "title": "Sem preço"},  # sem price -> descartado
        {"id": "2", "title": "Com preço", "price": 100},
    ]
    produtos = FonteFalsa(itens).buscar_produtos("q")
    assert [p.source_id for p in produtos] == ["2"]


def test_dados_incompletos_sem_id_sao_descartados():
    itens = [
        {"title": "Sem id", "price": 50},  # sem id -> descartado
        {"id": "9", "title": "Ok", "price": 50},
    ]
    produtos = FonteFalsa(itens).buscar_produtos("q")
    assert [p.source_id for p in produtos] == ["9"]


def test_produto_duplicado_mantem_so_o_primeiro():
    itens = [
        {"id": "1", "title": "Primeiro", "price": 100},
        {"id": "1", "title": "Duplicado", "price": 200},
    ]
    produtos = FonteFalsa(itens).buscar_produtos("q")
    assert len(produtos) == 1
    assert produtos[0].title == "Primeiro"


def test_preco_negativo_e_descartado():
    itens = [{"id": "1", "title": "Preço negativo", "price": -10}]
    assert FonteFalsa(itens).buscar_produtos("q") == []


def test_e_realmente_abstrata():
    with pytest.raises(TypeError):
        OfferSource()
