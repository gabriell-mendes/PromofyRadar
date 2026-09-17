"""Testes de app/storage.py: upsert por (source, source_id), status e
leitura de uma oferta específica (obter_oferta é usada por
app/collect.py pra decidir se uma oferta já foi vista com o mesmo
preço/desconto -- ver tests/test_collect.py pra essa regra).

Usa um arquivo de banco temporário (tmp_path do pytest) em vez do banco
real do projeto -- cada teste começa com um banco vazio, isolado dos
outros testes e dos dados reais em data/ofertas.db.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app import storage
from app.models import Product


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "teste_ofertas.db")
    storage.inicializar_banco()


def _produto(**overrides) -> Product:
    base = dict(
        source="mercadolivre",
        source_id="MLB123",
        title="Produto Teste",
        price=Decimal("100"),
        url="https://produto.mercadolivre.com.br/MLB123",
        store="Loja Teste",
        collected_at=datetime(2026, 1, 1),
    )
    base.update(overrides)
    return Product(**base)


def test_oferta_inexistente_devolve_none():
    assert storage.obter_oferta("mercadolivre", "MLB999") is None


def test_salvar_e_depois_obter_oferta():
    storage.salvar_oferta(_produto(), score=80, reason="motivo", desconto_percentual=30.0)
    oferta = storage.obter_oferta("mercadolivre", "MLB123")

    assert oferta is not None
    assert oferta["price"] == Decimal("100")
    assert oferta["desconto_percentual"] == 30.0
    assert oferta["status"] == storage.STATUS_PENDENTE


def test_salvar_de_novo_atualiza_sem_duplicar():
    storage.salvar_oferta(_produto(price=Decimal("100")), 80, "motivo", 30.0)
    storage.salvar_oferta(_produto(price=Decimal("90")), 85, "motivo novo", 40.0)

    todas = storage.listar_ofertas()
    assert len(todas) == 1
    assert todas[0]["price"] == Decimal("90")
    assert todas[0]["desconto_percentual"] == 40.0


def test_atualizar_nao_mexe_no_status_ja_marcado():
    storage.salvar_oferta(_produto(), 80, "motivo", 30.0)
    storage.marcar_status("mercadolivre", "MLB123", storage.STATUS_ENVIADA)

    storage.salvar_oferta(_produto(price=Decimal("80")), 85, "motivo novo", 40.0)

    assert storage.obter_status("mercadolivre", "MLB123") == storage.STATUS_ENVIADA


def test_marcar_status_muda_status_e_devolve_true():
    storage.salvar_oferta(_produto(), 80, "motivo", 30.0)
    assert storage.marcar_status("mercadolivre", "MLB123", storage.STATUS_ENVIADA) is True
    assert storage.obter_status("mercadolivre", "MLB123") == storage.STATUS_ENVIADA


def test_marcar_status_oferta_inexistente_devolve_false():
    assert storage.marcar_status("mercadolivre", "MLB999", storage.STATUS_ENVIADA) is False


def test_marcar_status_invalido_levanta_value_error():
    with pytest.raises(ValueError):
        storage.marcar_status("mercadolivre", "MLB123", "status-invalido")


def test_contar_por_status():
    storage.salvar_oferta(_produto(source_id="MLB1"), 80, "m", 30.0)
    storage.salvar_oferta(_produto(source_id="MLB2"), 80, "m", 30.0)
    storage.marcar_status("mercadolivre", "MLB1", storage.STATUS_ENVIADA)

    contagem = storage.contar_por_status()
    assert contagem == {storage.STATUS_PENDENTE: 1, storage.STATUS_ENVIADA: 1}
