# Grupo de Ofertas

Deal alerts + afiliados. Cada pessoa coleta ofertas do Mercado Livre no próprio PC (scraper com Playwright), revisa no painel local e envia as aprovadas a um painel online compartilhado (FastAPI + SQLite, num VPS, sem scraper). Dono do projeto: Gabriel, que usa o projeto também para aprender. Windows 11, PowerShell.

## Comandos (da raiz do projeto)
Use sempre o Python do projeto: `.venv\Scripts\python.exe`. O Python do sistema não tem FastAPI.

- Testes: `.venv\Scripts\python.exe -m pytest -q`
- Painel local (porta 5500): `.venv\Scripts\python.exe techdrop_server.py` ou `frontend\iniciar.bat`. Modo teste sem navegador: `frontend\iniciar_teste.bat`
- Painel online local: `$env:PAINEL_COOKIE_SECURE = "0"; .venv\Scripts\python.exe -m uvicorn painel_online.app:app --port 8000` (o `0` é só para testar em http)
- Criar admin do painel online: `.venv\Scripts\python.exe -m painel_online.cli criar-admin NOME` (a senha é pedida no teclado, não aceita pipe)

## Onde está cada coisa
- `techdrop_server.py` + `frontend/`: painel local. Roda os scrapers (`scraperd.py`, `scraper_categoria.py`, `scraper_ofertas.py`) e envia ao painel online
- `painel_online/`: painel online (schemas, upsert, ingest, auth, db, backup, cli, paginas)
- `deploy/` e `docs/deploy-vps.md`: serviço systemd, Caddyfile, cron de backup, roteiro do VPS
- `deal_score.py`, `pontuacao.py`, `historico.py`: Deal Score e histórico de preços (SQLite local)
- Mapa completo: `docs/estrutura-do-projeto.md`. Guia para usuários e glossário: `docs/compartilhamento-de-dados.md`
- Não use como referência: `docs/architecture.md`, `docs/data-model.md`, `docs/roadmap.md` e o `.env.example` antigo descrevem uma versão abandonada (`app/`). Deixe intocados

## Como trabalhar com o Gabriel
- Antes de cada etapa, explique em poucas linhas o objetivo, os conceitos e onde ela se encaixa. Etapas pequenas: pare ao fim, mostre o que mudou e como testar, e espere a confirmação
- Soluções simples, sem overengineering (nada de Redis, Celery, microserviços, OAuth, perfis de permissão sem necessidade). Diferencie sempre MVP, melhoria futura e desnecessário agora
- Valide com dados reais antes de avançar. Decisões quantitativas (Deal Score) por regras e dados, nunca por opinião de LLM
- Quando fizer sentido, deixe uma parte pequena para ele escrever e revise depois, explicando os erros
- Ao fim de cada etapa: rode os testes e mostre o resultado, escreva `docs/aprendizados/etapa-N.md` e atualize `docs/compartilhamento-de-dados.md`
- Só faça commit, push ou merge quando ele pedir. Estando em `main`, crie uma branch antes de commitar
- Escrita: português do Brasil, sem travessão (use vírgula, dois-pontos ou espaço). Emoji só para identificação visual rápida
- Terminal: PowerShell em linha única, comandos separados por `;`, nunca `&&`, explicação mínima. Comandos de servidor são Linux

## Decisões já fechadas (não reabrir sem motivo forte)
- SQLite no servidor. Produto identificado por `(loja, id_produto)`, com `id_produto` derivado da URL por `historico.chave_produto`
- `enviado_por` vem do token, nunca do cliente
- Duas credenciais separadas: token de API só envia (`/api/ingest`), cookie de sessão só administra. Sessões ficam no banco
- Envio ao painel é manual, com revisão. O token fica só no servidor local, nunca no navegador. Ofertas de teste (`teste: true`) nunca são enviadas
- Descartes do painel online são compartilhados. Descartes do painel local são só do PC
- Sem Docker por enquanto (reconsiderar com vários servidores)

## Cuidados
- Nunca commitar `.env`, `data/`, `browser_profile/`, `debug_snapshots/` nem arquivos `.db`. Nunca escrever token ou senha reais em arquivo versionado
- Testar envio ao painel grava a marca `enviado_painel_em` em `frontend/data/ofertas.json` (dados reais do Gabriel). Faça backup antes e restaure depois
- Coleta: respeitar termos de uso e limites. Não adicionar técnicas para burlar CAPTCHA, autenticação ou anti-bot. Se uma fonte bloquear, o caminho é API oficial ou reduzir a frequência
- Todo pacote que o código importa precisa estar em `requirements.txt` (o do servidor é `requirements-painel.txt`, sem Playwright). Confirme instalando num venv limpo
