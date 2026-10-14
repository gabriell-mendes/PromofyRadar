# Etapa 8: botão "Enviar ao Telegram"

## Objetivo
Publicar no grupo do Telegram a mensagem que você revisou no preview, com um clique. Continua manual: uma oferta, uma mensagem, depois de você olhar.

## Conceitos
- **Bot do Telegram**: um "usuário" controlado por código. Você cria no @BotFather e recebe um token (a senha do bot). O bot só posta em grupo ou canal onde é administrador.
- **chat_id**: o endereço do grupo/canal. Em grupo é negativo; em canal costuma começar com `-100`. O comando `telegram_envio.py descobrir-chat` mostra o id (mande uma mensagem no grupo antes).
- **Token fica no servidor**: o navegador só manda o texto ao seu servidor local (`/api/telegram/enviar`); o servidor é quem fala com o Telegram. Mesmo desenho do token do painel online.
- **Link de afiliado continua manual**: o preview agora é editável. Troque o link pelo de afiliado antes de enviar.

## O que mudou
- `telegram_envio.py`: `enviar_mensagem` e `descobrir_chats` (lê `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` do `.env`; erros em português, sem vazar o token).
- `techdrop_server.py`: `GET /api/telegram/status` e `POST /api/telegram/enviar` (exige o header `X-TechDrop`, limite de 4096 caracteres).
- `frontend`: botão "Enviar ao Telegram" no preview, preview editável, confirmação antes de enviar, marca "enviado" depois.
- Testes: `tests/test_telegram_envio.py` e `tests/test_telegram_painel_local.py`.

## Como testar
1. `.venv\Scripts\python.exe -m pytest -q`
2. Preencha o `.env`, rode `.venv\Scripts\python.exe telegram_envio.py enviar "teste"`.
3. Abra o painel, clique numa oferta, edite o texto, "Enviar ao Telegram".

## MVP, melhoria futura, desnecessário agora
- MVP: o que está acima.
- Futuro: envio em lote com intervalo entre mensagens, foto da oferta, registro de cliques por link.
- Desnecessário agora: fila, agendamento, publicação automática sem revisão.
