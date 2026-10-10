"""Senhas de administradores: validar regras e guardar/conferir com bcrypt.

bcrypt é lento de propósito (milhares de vezes mais que sha256): quem roubar o banco
precisa gastar muito tempo por tentativa, e senha humana é fraca o bastante para
isso importar. Tokens de API são aleatórios e fortes, por isso usam sha256 (ver db.py).
"""

import os

import bcrypt

SENHA_MIN = 10
SENHA_MAX_BYTES = 72  # limite do próprio bcrypt: além disso ele ignora (ou recusa) o resto
BCRYPT_ROUNDS = int(os.environ.get("PAINEL_BCRYPT_ROUNDS", "12"))


def validar_senha(senha: str) -> str | None:
    """Devolve a mensagem de erro, ou None se a senha serve."""
    if len(senha) < SENHA_MIN:
        return f"A senha precisa ter pelo menos {SENHA_MIN} caracteres."
    if len(senha.encode()) > SENHA_MAX_BYTES:
        return f"A senha pode ter no máximo {SENHA_MAX_BYTES} bytes."
    return None


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verificar_senha(senha: str, hash_guardado: str | None) -> bool:
    """Confere a senha. Para usuário inexistente (hash None) ainda gasta o mesmo tempo,
    para o tempo de resposta não revelar quais usuários existem."""
    alvo = hash_guardado or _hash_falso()
    try:
        ok = bcrypt.checkpw(senha.encode()[:SENHA_MAX_BYTES], alvo.encode())
    except ValueError:
        return False
    return ok and hash_guardado is not None


_falso: str | None = None


def _hash_falso() -> str:
    global _falso
    if _falso is None:
        _falso = hash_senha("senha-falsa-so-para-gastar-tempo")
    return _falso
