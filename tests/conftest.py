"""Fixtures do painel online (Etapas 2 e 3)."""

import pytest
from fastapi.testclient import TestClient

from painel_online import credenciais
from painel_online.app import criar_app
from painel_online.db import conectar, criar_token, criar_usuario

SENHA = "senha-de-teste-1"


class Painel:
    def __init__(self, app, con):
        self.app = app
        self.con = con
        self.ids: dict[str, int] = {}

    def cliente(self, com_header: bool = True) -> TestClient:
        # https: o cookie é Secure e o cliente só o devolve por HTTPS, como o navegador.
        # O header X-TechDrop é o que a página envia (proteção CSRF).
        headers = {"X-TechDrop": "1"} if com_header else {}
        return TestClient(self.app, base_url="https://testserver", headers=headers)

    def admin(self, nome: str, senha: str = SENHA) -> int:
        self.ids[nome] = criar_usuario(self.con, nome, senha)
        return self.ids[nome]

    def entrar(self, nome: str, senha: str = SENHA) -> TestClient:
        """Cliente novo (cookies próprios) já logado como `nome`."""
        c = self.cliente()
        r = c.post("/api/login", json={"nome": nome, "senha": senha})
        assert r.status_code == 200, r.text
        return c

    def token(self, nome: str, rotulo: str = "pc") -> str:
        return criar_token(self.con, self.ids[nome], rotulo)[1]


@pytest.fixture
def painel(tmp_path, monkeypatch):
    monkeypatch.setattr(credenciais, "BCRYPT_ROUNDS", 4)  # bcrypt rápido só nos testes
    db = tmp_path / "painel.db"
    app = criar_app(db)
    con = conectar(db)
    yield Painel(app, con)
    con.close()
