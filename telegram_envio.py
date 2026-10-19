r"""Envio de mensagens ao Telegram (Bot API). Só precisa de TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env.

Uso (PowerShell, da raiz do projeto):
  .\.venv\Scripts\python.exe telegram_envio.py configurar-perfil   # preenche About e Description do bot
  .\.venv\Scripts\python.exe telegram_envio.py descobrir-chat      # lista os chat ids que o bot enxerga
  .\.venv\Scripts\python.exe telegram_envio.py verificar           # confere token, chat e se o bot é admin
  .\.venv\Scripts\python.exe telegram_envio.py enviar "texto"      # manda uma mensagem de teste

O token fica só no .env (nunca no código, nunca no navegador) e nunca aparece em mensagens de erro.
"""

import os
import sys
from pathlib import Path
import requests
from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parent / ".env"
API = "https://api.telegram.org"
TIMEOUT = 15


def _config() -> tuple[str, str]:
    """(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID). Lê do ambiente e do `.env`."""
    arquivo = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or arquivo.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or arquivo.get("TELEGRAM_CHAT_ID") or "").strip()
    return token, chat


def enviar_mensagem(texto: str, *, post=requests.post) -> tuple[bool, str | None]:
    """Envia `texto` ao chat configurado. Devolve (ok, erro_em_portugues)."""
    token, chat = _config()
    if not token or not chat:
        return False, "Telegram não configurado. Preencha TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env."
    if not texto.strip():
        return False, "Mensagem vazia."
    try:
        r = post(
            f"{API}/bot{token}/sendMessage",
            json={"chat_id": chat, "text": texto, "disable_web_page_preview": False},
            timeout=TIMEOUT,
            allow_redirects=False,
        )
    except requests.exceptions.RequestException:
        return False, "Não consegui falar com o Telegram. Confira sua internet."
    if r.status_code == 200:
        return True, None
    if r.status_code == 401:
        return False, "Token do bot inválido. Gere outro no @BotFather e atualize o .env."
    if r.status_code in (400, 403):
        return False, "O Telegram recusou: confira o TELEGRAM_CHAT_ID e se o bot é administrador do grupo/canal."
    if r.status_code == 429:
        return False, "Muitas mensagens em pouco tempo. Aguarde um pouco e tente de novo."
    return False, f"O Telegram respondeu com erro {r.status_code}."


def descobrir_chats(*, get=requests.get) -> tuple[list[tuple[str, str]], str | None]:
    """Lista (chat_id, nome) dos chats que mandaram algo ao bot. Mande uma mensagem no grupo antes."""
    token, _ = _config()
    if not token:
        return [], "Preencha TELEGRAM_BOT_TOKEN no .env."
    try:
        r = get(f"{API}/bot{token}/getUpdates", timeout=TIMEOUT, allow_redirects=False)
    except requests.exceptions.RequestException:
        return [], "Não consegui falar com o Telegram. Confira sua internet."
    if r.status_code == 401:
        return [], "Token do bot inválido."
    if r.status_code != 200:
        return [], f"O Telegram respondeu com erro {r.status_code}."
    vistos: dict[str, str] = {}
    for u in r.json().get("result", []):
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            vistos[str(chat["id"])] = chat.get("title") or chat.get("username") or chat.get("first_name") or ""
    return list(vistos.items()), None


PERFIL_SOBRE = "Ofertas de tecnologia selecionadas à mão pelo TechDrop."  # limite do Telegram: 120
PERFIL_DESCRICAO = (  # limite do Telegram: 512
    "Este bot publica no grupo as ofertas de tecnologia que o TechDrop revisou: "
    "preço, desconto e link da loja. Ele só envia mensagens, não responde a comandos."
)


def _chamar(metodo: str, corpo: dict | None = None, *, post=requests.post) -> tuple[dict | None, str | None]:
    """Chama um método da Bot API. Devolve (campo `result`, erro_em_portugues). Nunca vaza o token."""
    token, _ = _config()
    if not token:
        return None, "Preencha TELEGRAM_BOT_TOKEN no .env."
    try:
        r = post(f"{API}/bot{token}/{metodo}", json=corpo or {}, timeout=TIMEOUT, allow_redirects=False)
    except requests.exceptions.RequestException:
        return None, "Não consegui falar com o Telegram. Confira sua internet."
    if r.status_code == 401:
        return None, "Token do bot inválido. Gere outro no @BotFather e atualize o .env."
    if r.status_code != 200:
        return None, f"O Telegram respondeu com erro {r.status_code} em {metodo}."
    return r.json().get("result"), None


def verificar(*, post=requests.post) -> tuple[list[str], bool]:
    """Confere a configuração de envio. Devolve (linhas para mostrar, tudo_ok)."""
    bot, erro = _chamar("getMe", post=post)
    if erro:
        return [f"❌ Token: {erro}"], False
    linhas = [f"✅ Token válido: @{bot.get('username')} ({bot.get('first_name')})"]
    _, chat = _config()
    if not chat:
        return linhas + ["❌ TELEGRAM_CHAT_ID vazio. Rode o comando descobrir-chat e preencha o .env."], False
    membro, erro = _chamar("getChatMember", {"chat_id": chat, "user_id": bot["id"]}, post=post)
    if erro:
        return linhas + ["❌ Chat: o bot não enxerga esse chat. Confira o TELEGRAM_CHAT_ID e se o bot foi adicionado."], False
    status = (membro or {}).get("status")
    if status not in ("administrator", "creator"):
        return linhas + [f"❌ Chat: o bot está como '{status}'. Torne-o administrador do grupo/canal."], False
    return linhas + [f"✅ Chat {chat}: o bot é administrador e pode postar."], True


def configurar_perfil(*, post=requests.post) -> tuple[bool, str | None]:
    """Preenche About e Description do bot (o que o @BotFather chama de Edit About / Edit Description)."""
    for metodo, campo, texto in (
        ("setMyShortDescription", "short_description", PERFIL_SOBRE),
        ("setMyDescription", "description", PERFIL_DESCRICAO),
    ):
        _, erro = _chamar(metodo, {campo: texto}, post=post)
        if erro:
            return False, erro
    return True, None


def _cli(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "verificar":
        linhas, ok = verificar()
        print("\n".join(linhas))
        return 0 if ok else 1
    if len(argv) >= 2 and argv[1] == "configurar-perfil":
        ok, erro = configurar_perfil()
        print("Perfil do bot atualizado (About e Description)." if ok else erro)
        return 0 if ok else 1
    if len(argv) >= 2 and argv[1] == "descobrir-chat":
        chats, erro = descobrir_chats()
        if erro:
            print(erro)
            return 1
        if not chats:
            print("Nenhum chat ainda. Adicione o bot ao grupo, mande uma mensagem lá e rode de novo.")
            return 1
        for chat_id, nome in chats:
            print(f"{chat_id}\t{nome}")
        return 0
    if len(argv) >= 3 and argv[1] == "enviar":
        ok, erro = enviar_mensagem(" ".join(argv[2:]))
        print("Enviado." if ok else erro)
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
