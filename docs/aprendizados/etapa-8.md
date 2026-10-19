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

## Configurar o bot (passo a passo)
O bot `@techdropblogbot` já existe. Falta ligar ele ao grupo e ao seu `.env`. Tudo no PowerShell, da raiz do projeto.

1. No Telegram, abra o @BotFather, `/mybots`, escolha o bot, **API Token**. Copie o token. É a senha do bot: não mostre a ninguém.
2. Crie o `.env` (copie do `.env.example`) e preencha só a linha `TELEGRAM_BOT_TOKEN=`.
3. Preencha o perfil do bot (equivale a "Edit About" e "Edit Description" do BotFather): `.venv\Scripts\python.exe telegram_envio.py configurar-perfil`
4. Crie o grupo (ou canal), adicione o bot e **torne-o administrador** (em canal isso é obrigatório para postar). Mande qualquer mensagem no grupo.
5. Descubra o id do grupo: `.venv\Scripts\python.exe telegram_envio.py descobrir-chat`. Copie o número (negativo) para `TELEGRAM_CHAT_ID=` no `.env`.
6. Confira tudo: `.venv\Scripts\python.exe telegram_envio.py verificar`. Deve mostrar três ✅.
7. Teste real: `.venv\Scripts\python.exe telegram_envio.py enviar "teste"`.

Fica manual no BotFather (a API não faz): foto do bot (Edit Botpic) e Privacy Policy. Não são necessárias para enviar.

Comandos (`/start`, etc.) não foram criados de propósito: o bot só envia, não responde a ninguém.

## MVP, melhoria futura, desnecessário agora
- MVP: o que está acima.
- Futuro: envio em lote com intervalo entre mensagens, foto da oferta, registro de cliques por link.
- Desnecessário agora: fila, agendamento, publicação automática sem revisão.
