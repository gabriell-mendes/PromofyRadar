"""Administração pelo terminal, no servidor (ou no seu PC, para testar).

    .venv\\Scripts\\python.exe -m painel_online.cli criar-admin NOME
    .venv\\Scripts\\python.exe -m painel_online.cli redefinir-senha NOME

A senha é pedida no terminal (não aparece na tela e não fica no histórico de comandos).
Todo usuário é administrador: não há perfis de permissão no MVP. Os tokens de API cada
pessoa gera sozinha, depois de entrar, na página /tokens.
"""

import getpass
import sqlite3
import sys

from .db import caminho_db, conectar, criar_tabelas, criar_usuario, redefinir_senha

USO = "Uso: python -m painel_online.cli [criar-admin|redefinir-senha] NOME"


def _pedir_senha() -> str | None:
    senha = getpass.getpass("Senha (mínimo 10 caracteres): ")
    if getpass.getpass("Repita a senha: ") != senha:
        print("As senhas não conferem.")
        return None
    return senha


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("criar-admin", "redefinir-senha") or not argv[2].strip():
        print(USO)
        return 1
    comando, nome = argv[1], argv[2].strip()
    senha = _pedir_senha()
    if senha is None:
        return 1
    con = conectar(caminho_db())
    criar_tabelas(con)
    try:
        if comando == "criar-admin":
            criar_usuario(con, nome, senha)
            print(f"Administrador '{nome}' criado. Entre pelo navegador em /login.")
        elif redefinir_senha(con, nome, senha):
            print(f"Senha de '{nome}' redefinida. Sessões abertas foram encerradas.")
        else:
            print(f"Usuário '{nome}' não existe.")
            return 1
    except sqlite3.IntegrityError:
        print(f"O usuário '{nome}' já existe. Para trocar a senha: redefinir-senha {nome}")
        return 1
    except ValueError as e:
        print(e)
        return 1
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
