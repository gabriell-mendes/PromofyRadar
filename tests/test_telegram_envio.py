"""Envio ao Telegram: sem rede (post/get falsos) e sem token real."""

import requests

import telegram_envio as tg


class Resp:
    def __init__(self, status=200, dados=None):
        self.status_code = status
        self._dados = dados or {}

    def json(self):
        return self._dados


def _config(monkeypatch, token="123:ABC", chat="-100999"):
    monkeypatch.setattr(tg, "ENV_FILE", tg.Path("/nao/existe/.env"))
    for k, v in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat)):
        if v:
            monkeypatch.setenv(k, v)
        else:
            monkeypatch.delenv(k, raising=False)


def test_sem_configuracao(monkeypatch):
    _config(monkeypatch, token="", chat="")
    ok, erro = tg.enviar_mensagem("oi", post=lambda *a, **k: Resp())
    assert not ok and "TELEGRAM_BOT_TOKEN" in erro


def test_envio_ok_usa_token_na_url_e_chat_no_corpo(monkeypatch):
    _config(monkeypatch)
    visto = {}

    def post(url, json, timeout, allow_redirects):
        visto.update(url=url, json=json, redirect=allow_redirects)
        return Resp(200)

    assert tg.enviar_mensagem("oferta", post=post) == (True, None)
    assert visto["url"].endswith("/bot123:ABC/sendMessage")
    assert visto["json"]["chat_id"] == "-100999" and visto["json"]["text"] == "oferta"
    assert visto["redirect"] is False


def test_erros_traduzidos_e_sem_vazar_token(monkeypatch):
    _config(monkeypatch)
    for status, trecho in ((401, "Token do bot inválido"), (403, "TELEGRAM_CHAT_ID"), (429, "Aguarde"), (500, "500")):
        ok, erro = tg.enviar_mensagem("x", post=lambda *a, **k: Resp(status))
        assert not ok and trecho in erro and "123:ABC" not in erro


def test_falha_de_rede_nao_vaza_token(monkeypatch):
    _config(monkeypatch)

    def post(*a, **k):
        raise requests.exceptions.ConnectionError("https://api.telegram.org/bot123:ABC/sendMessage")

    ok, erro = tg.enviar_mensagem("x", post=post)
    assert not ok and "123:ABC" not in erro


def test_descobrir_chats(monkeypatch):
    _config(monkeypatch, chat="")
    dados = {"result": [
        {"message": {"chat": {"id": -100111, "title": "Grupo Ofertas"}}},
        {"channel_post": {"chat": {"id": -100222, "title": "Canal"}}},
        {"message": {"chat": {"id": -100111, "title": "Grupo Ofertas"}}},
    ]}
    chats, erro = tg.descobrir_chats(get=lambda *a, **k: Resp(200, dados))
    assert erro is None and chats == [("-100111", "Grupo Ofertas"), ("-100222", "Canal")]
