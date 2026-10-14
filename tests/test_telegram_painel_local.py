"""Painel local: endpoints do Telegram (sem rede; o envio real é trocado por um falso)."""

from fastapi.testclient import TestClient

import techdrop_server as srv

H = {"X-TechDrop": "1"}


def _cliente():
    return TestClient(srv.app)


def test_status_nao_vaza_credenciais(monkeypatch):
    monkeypatch.setattr(srv.telegram_envio, "_config", lambda: ("123:ABC", "-100999"))
    r = _cliente().get("/api/telegram/status")
    assert r.json() == {"configurado": True}
    assert "123:ABC" not in r.text


def test_status_sem_configuracao(monkeypatch):
    monkeypatch.setattr(srv.telegram_envio, "_config", lambda: ("", ""))
    assert _cliente().get("/api/telegram/status").json() == {"configurado": False}


def test_enviar_exige_header_do_painel():
    assert _cliente().post("/api/telegram/enviar", json={"texto": "oi"}).status_code == 403


def test_enviar_ok_repassa_o_texto(monkeypatch):
    vistos = []
    monkeypatch.setattr(srv.telegram_envio, "enviar_mensagem", lambda t: (vistos.append(t), (True, None))[1])
    r = _cliente().post("/api/telegram/enviar", json={"texto": "  OFERTA X  "}, headers=H)
    assert r.status_code == 200 and vistos == ["OFERTA X"]


def test_enviar_vazio_e_grande_demais(monkeypatch):
    monkeypatch.setattr(srv.telegram_envio, "enviar_mensagem", lambda t: (True, None))
    assert _cliente().post("/api/telegram/enviar", json={"texto": "  "}, headers=H).status_code == 400
    r = _cliente().post("/api/telegram/enviar", json={"texto": "x" * 4097}, headers=H)
    assert r.status_code == 400 and "grande demais" in r.json()["detail"]


def test_erros_do_telegram_viram_mensagem_clara(monkeypatch):
    monkeypatch.setattr(srv.telegram_envio, "enviar_mensagem", lambda t: (False, "Telegram não configurado. Preencha ..."))
    assert _cliente().post("/api/telegram/enviar", json={"texto": "oi"}, headers=H).status_code == 400
    monkeypatch.setattr(srv.telegram_envio, "enviar_mensagem", lambda t: (False, "Token do bot inválido."))
    r = _cliente().post("/api/telegram/enviar", json={"texto": "oi"}, headers=H)
    assert r.status_code == 502 and "Token do bot inválido" in r.json()["detail"]
