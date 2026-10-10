"""Etapa 4: o painel local envia ofertas ao painel online (servidor de verdade, em thread)."""

import json
import socket
import threading
import time

import pytest
import requests
import uvicorn
from fastapi.testclient import TestClient

import techdrop_server as srv


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def online(painel):
    """Painel online rodando de verdade em localhost, com um admin e um token de PC."""
    painel.admin("ana")
    token = painel.token("ana", "PC da Ana")
    porta = _porta_livre()
    servidor = uvicorn.Server(uvicorn.Config(painel.app, host="127.0.0.1", port=porta, log_level="error"))
    thread = threading.Thread(target=servidor.run, daemon=True)
    thread.start()
    for _ in range(100):
        if servidor.started:
            break
        time.sleep(0.05)
    assert servidor.started
    yield {"url": f"http://127.0.0.1:{porta}", "token": token, "painel": painel}
    servidor.should_exit = True
    thread.join(timeout=5)


def oferta(n: int, **extra) -> dict:
    return {
        "title": f"Produto {n}",
        "price": 100.0 + n,
        "old_price": 200.0 + n,
        "discount": 50.0,
        "installment": "10x sem juros",
        "link": f"https://www.mercadolivre.com.br/produto-{n}/p/MLB{20000000 + n}?pdp_filters=x",
        "image": f"https://http2.mlstatic.com/img{n}.webp",
        "deal_score": 40 + n,
        "deal_confianca": "baixa",
        "deal_motivos": ["motivo"],
        "deal_flags": [],
        **extra,
    }


@pytest.fixture
def local(tmp_path, monkeypatch):
    """Servidor local apontando para uma pasta de dados temporária e sem .env."""
    dados = tmp_path / "data"
    dados.mkdir()
    monkeypatch.setattr(srv, "DATA_DIR", dados)
    monkeypatch.setattr(srv, "OFERTAS_JSON", dados / "ofertas.json")
    monkeypatch.setattr(srv, "DESCARTADOS_JSON", dados / "descartados.json")
    monkeypatch.setattr(srv, "ENV_FILE", tmp_path / ".env")
    monkeypatch.delenv("PAINEL_URL", raising=False)
    monkeypatch.delenv("PAINEL_TOKEN", raising=False)
    return TestClient(srv.app, headers={"X-TechDrop": "1"})


def gravar(ofertas: list[dict]):
    srv.OFERTAS_JSON.write_text(json.dumps(ofertas), encoding="utf-8")


def lidas() -> list[dict]:
    return json.loads(srv.OFERTAS_JSON.read_text(encoding="utf-8"))


def configurar(monkeypatch, online, token=None, url=None):
    monkeypatch.setenv("PAINEL_URL", url or online["url"])
    monkeypatch.setenv("PAINEL_TOKEN", token or online["token"])


# ---------- configuração ----------
def test_status_sem_configuracao(local):
    assert local.get("/api/painel/status").json() == {"configurado": False, "url": None}


def test_status_configurado_nunca_mostra_o_token(local, monkeypatch, online):
    configurar(monkeypatch, online)
    r = local.get("/api/painel/status")
    assert r.json() == {"configurado": True, "url": online["url"]}
    assert online["token"] not in r.text


def test_le_o_env_sem_copiar_o_token_para_o_ambiente(local, tmp_path):
    import os

    (tmp_path / ".env").write_text("PAINEL_URL=https://painel.exemplo.com/\nPAINEL_TOKEN=td_abc\n", encoding="utf-8")
    assert local.get("/api/painel/status").json() == {"configurado": True, "url": "https://painel.exemplo.com"}
    assert "PAINEL_TOKEN" not in os.environ  # senão iria junto para o processo do scraper


def test_enviar_sem_configurar_explica_o_que_fazer(local):
    gravar([oferta(1)])
    r = local.post("/api/painel/enviar", json={})
    assert r.status_code == 400 and "PAINEL_URL" in r.json()["detail"]


def test_recusa_http_em_host_remoto(local, monkeypatch):
    gravar([oferta(1)])
    monkeypatch.setenv("PAINEL_URL", "http://painel.exemplo.com")
    monkeypatch.setenv("PAINEL_TOKEN", "td_x")
    r = local.post("/api/painel/enviar", json={})
    assert r.status_code == 400 and "https" in r.json()["detail"]
    assert srv._validar_url_painel("http://localhost:8000") is None
    assert srv._validar_url_painel("https://painel.exemplo.com") is None
    assert srv._validar_url_painel("ftp://x") is not None


def test_enviar_exige_o_header_anti_csrf(local):
    r = local.post("/api/painel/enviar", json={}, headers={"X-TechDrop": ""})
    assert r.status_code == 403


# ---------- envio ----------
def test_envio_completo_mapeia_os_campos_e_marca_como_enviado(local, monkeypatch, online):
    configurar(monkeypatch, online)
    gravar([oferta(1, category="Tecnologia"), oferta(2, old_price=0, deal_score=None), oferta(3)])

    r = local.post("/api/painel/enviar", json={})
    assert r.status_code == 200, r.text
    res = r.json()
    assert (res["criadas"], res["atualizadas"], res["ignoradas"]) == (3, 0, 0)
    assert online["token"] not in r.text

    admin = online["painel"].entrar("ana")
    por_titulo = {o["titulo"]: o for o in admin.get("/api/ofertas").json()["ofertas"]}
    o1, o2 = por_titulo["Produto 1"], por_titulo["Produto 2"]
    assert o1["id_produto"] == "MLB20000001" and o1["preco"] == 101.0 and o1["preco_original"] == 201.0
    assert o1["categoria"] == "Tecnologia" and o1["deal_score"] == 41 and o1["deal_motivos"] == ["motivo"]
    assert o1["enviado_por"] == "ana" and o1["coletado_em"]
    assert o2["preco_original"] is None and o2["deal_score"] is None  # old_price 0 vira "sem preço original"

    assert all(o["enviado_painel_em"] for o in lidas())
    # "enviar todas" só manda as pendentes: agora não sobra nada
    assert local.post("/api/painel/enviar", json={}).status_code == 400


def test_reenviar_selecionada_atualiza_e_soma_historico(local, monkeypatch, online):
    configurar(monkeypatch, online)
    gravar([oferta(1)])
    local.post("/api/painel/enviar", json={})
    r = local.post("/api/painel/enviar", json={"links": [oferta(1)["link"]]})
    assert (r.json()["criadas"], r.json()["atualizadas"]) == (0, 1)
    admin = online["painel"].entrar("ana")
    o = admin.get("/api/ofertas").json()["ofertas"][0]
    assert o["n_precos"] == 2


def test_so_envia_as_selecionadas(local, monkeypatch, online):
    configurar(monkeypatch, online)
    gravar([oferta(1), oferta(2), oferta(3)])
    r = local.post("/api/painel/enviar", json={"links": [oferta(2)["link"]]})
    assert r.json()["criadas"] == 1
    marcadas = {o["title"]: bool(o.get("enviado_painel_em")) for o in lidas()}
    assert marcadas == {"Produto 1": False, "Produto 2": True, "Produto 3": False}


def test_oferta_de_teste_nunca_vai_ao_painel_real(local, monkeypatch, online):
    configurar(monkeypatch, online)
    gravar([oferta(1), oferta(2, teste=True)])
    r = local.post("/api/painel/enviar", json={"links": [oferta(1)["link"], oferta(2)["link"]]}).json()
    assert (r["criadas"], r["de_teste"]) == (1, 1)
    assert online["painel"].entrar("ana").get("/api/ofertas").json()["total"] == 1

    gravar([oferta(3, teste=True)])
    assert local.post("/api/painel/enviar", json={}).status_code == 400


def test_oferta_recusada_pelo_painel_aparece_com_titulo_e_nao_e_marcada(local, monkeypatch, online):
    configurar(monkeypatch, online)
    gravar([oferta(1), oferta(2, price=0)])
    res = local.post("/api/painel/enviar", json={}).json()
    assert (res["criadas"], res["ignoradas"]) == (1, 1)
    assert res["detalhes_ignoradas"][0]["titulo"] == "Produto 2" and "preco" in res["detalhes_ignoradas"][0]["motivo"]
    marcadas = {o["title"]: bool(o.get("enviado_painel_em")) for o in lidas()}
    assert marcadas == {"Produto 1": True, "Produto 2": False}


def test_envio_em_lotes(local, monkeypatch, online):
    configurar(monkeypatch, online)
    monkeypatch.setattr(srv, "LOTE_PAINEL", 2)
    gravar([oferta(n) for n in range(1, 6)])
    res = local.post("/api/painel/enviar", json={}).json()
    assert res["criadas"] == 5
    assert online["painel"].entrar("ana").get("/api/ofertas").json()["total"] == 5


# ---------- erros com mensagem clara ----------
def test_token_errado_ou_revogado(local, monkeypatch, online):
    gravar([oferta(1)])
    configurar(monkeypatch, online, token="td_token-que-nao-existe")
    r = local.post("/api/painel/enviar", json={})
    assert r.status_code == 401 and "Meus tokens" in r.json()["detail"] and "PAINEL_TOKEN" in r.json()["detail"]

    configurar(monkeypatch, online)
    online["painel"].con.execute("UPDATE tokens_api SET revogado_em = '2026-01-01'")
    assert local.post("/api/painel/enviar", json={}).status_code == 401
    assert not lidas()[0].get("enviado_painel_em")


def test_painel_fora_do_ar(local, monkeypatch, online):
    gravar([oferta(1)])
    configurar(monkeypatch, online, url=f"http://127.0.0.1:{_porta_livre()}")
    r = local.post("/api/painel/enviar", json={})
    assert r.status_code == 502 and "conectar" in r.json()["detail"]
    assert not lidas()[0].get("enviado_painel_em")


def test_falha_no_meio_avisa_quantas_ja_chegaram(local, monkeypatch, online):
    configurar(monkeypatch, online)
    monkeypatch.setattr(srv, "LOTE_PAINEL", 2)
    gravar([oferta(n) for n in range(1, 6)])
    real, chamadas = requests.post, []

    def post_que_cai_no_segundo_lote(*a, **kw):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise requests.exceptions.ConnectionError("caiu")
        return real(*a, **kw)

    monkeypatch.setattr(srv.requests, "post", post_que_cai_no_segundo_lote)
    r = local.post("/api/painel/enviar", json={})
    assert r.status_code == 502 and "Já chegaram 2" in r.json()["detail"] and "sem duplicar" in r.json()["detail"]
    assert sum(bool(o.get("enviado_painel_em")) for o in lidas()) == 2

    # reenviar o que falta funciona e não duplica
    monkeypatch.setattr(srv.requests, "post", real)
    res = local.post("/api/painel/enviar", json={}).json()
    assert res["criadas"] == 3
    assert online["painel"].entrar("ana").get("/api/ofertas").json()["total"] == 5


def test_mensagens_por_status_http():
    assert srv._erro_painel(401)[0] == 401
    assert "redirecionou" in srv._erro_painel(301)[1]
    assert "problema" in srv._erro_painel(503)[1]
    assert "formato ou o tamanho" in srv._erro_painel(413)[1]
