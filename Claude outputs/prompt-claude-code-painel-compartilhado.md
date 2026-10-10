# Prompt para o Claude Code: painel TechDrop compartilhado

Cole tudo abaixo no Claude Code, com a pasta `grupo-de-ofertas` aberta na raiz.

---

## 1. Contexto

Sou o Gabriel. Este é o projeto Grupo de Ofertas (deal alerts + afiliados). Já existe um painel local, `techdrop_server.py` (FastAPI) servindo a pasta `frontend/`, que executa o scraper (`scraperd.py`, `scraper_categoria.py`, `scraper_ofertas.py`) como processo separado e grava as ofertas em `frontend/data/ofertas.json` e `frontend/data/descartados.json`.

Quero evoluir para este modelo:

- Cada pessoa que usa o sistema roda o painel e o scraper **no próprio PC** (usa o próprio IP e o próprio navegador).
- Existe um **painel online hospedado em um VPS da Hostinger (KVM)**, que todos os administradores acessam.
- No painel local, a pessoa revisa as ofertas raspadas e clica em **"Enviar ao painel"**. As ofertas aprovadas vão para o painel online, onde todos os admins veem tudo junto.
- O VPS **não roda scraper e não usa Playwright**. Ele só recebe, guarda, deduplica e exibe.

## 2. Princípios do projeto (obrigatórios)

Eu quero aprender enquanto construo, então siga estas regras ao longo de todo o trabalho:

1. Antes de implementar cada etapa, explique em poucas linhas o objetivo, os conceitos necessários e onde ela se encaixa na arquitetura.
2. Trabalhe em etapas pequenas. **Pare ao fim de cada etapa**, mostre o que mudou, como testar, e espere eu confirmar antes de seguir.
3. Prefira soluções simples e compreensíveis. Sem overengineering: nada de Redis, Celery, microserviços, OAuth ou permissões por perfil neste momento.
4. Quando fizer sentido, deixe uma parte pequena para eu tentar implementar (por exemplo, o modelo `OfertaIn` ou a função de upsert) e revise meu código depois, explicando os erros.
5. Diferencie sempre o que é MVP, o que é melhoria futura e o que é desnecessário agora.
6. Valide cada etapa com dados reais (um `ofertas.json` verdadeiro) antes de avançar.
7. Decisões quantitativas (como Deal Score) continuam baseadas em dados e regras explícitas, sem LLM opinando.
8. Coleta: respeitar termos de uso e limites das fontes. **Não propor nem implementar técnicas para burlar CAPTCHA, autenticação ou anti-bot.** Se uma fonte bloquear, o caminho é API oficial ou reduzir a frequência, nunca contornar.
9. Comandos de terminal que você me passar devem ser **PowerShell em linha única, separados por ponto e vírgula** (nunca `&&`), diretos e com explicação mínima.
10. Escrita: sem travessão (use vírgula, dois-pontos ou espaço). Emojis só quando servirem de identificação visual rápida.

## 3. Arquitetura alvo

```
PC A (techdrop local + scraper) --\
PC B (techdrop local + scraper) ---+--> HTTPS POST /api/ingest (Bearer token) --> Painel online (VPS)
PC C (techdrop local + scraper) --/                                                    |
                                                                    login (cookie) <-- todos os admins
```

Decisões já tomadas (não reabrir sem motivo forte):

| Ponto | Decisão |
|---|---|
| Armazenamento no VPS | SQLite (não JSON), por causa de escrita concorrente de vários PCs |
| Produto repetido | Upsert pela chave única (loja + id_produto) |
| Preços | Cada envio gera uma linha em `precos` (produto, preço, data, enviado_por), formando histórico |
| Autoria | Campo `enviado_por` em cada oferta e em cada preço |
| Descartados | Ficam no VPS e são compartilhados entre todos os admins |
| Acesso de pessoas | Login usuário/senha (hash com bcrypt), sessão por cookie |
| Acesso dos PCs | Token de API por usuário, header `Authorization: Bearer`, guardado com hash no banco e revogável |
| Envio | Manual, por botão no painel local (revisão antes de enviar). Envio automático fica para depois |
| Hospedagem | VPS Ubuntu, uvicorn em `127.0.0.1` via systemd, Caddy na frente com HTTPS automático. Sem Docker por enquanto |

Fora do MVP: OAuth, recuperação de senha por e-mail, filas, permissões por perfil, sincronização do VPS de volta para os PCs, envio automático, dashboard avançado.

## 4. Etapas (executar nesta ordem, uma por vez)

**Etapa 0, leitura e plano.** Leia o repositório (`techdrop_server.py`, `frontend/`, `docs/architecture.md`, `docs/data-model.md`, `.gitignore`, `.env.example`). Me devolva um plano curto confirmando o que entendeu e quais arquivos serão criados ou alterados. Não altere nada ainda.

**Etapa 1, contrato do envio.** Abra um `ofertas.json` real e defina o formato do JSON que cada PC envia (`loja`, `id_produto`, `titulo`, `preco`, `preco_original`, `desconto`, `url`, `imagem`, `coletado_em` e o que mais o scraper já produz). Aqui eu escrevo o modelo pydantic `OfertaIn` e a função que decide "novo ou já existe". Explique os conceitos, me deixe tentar e revise.

**Etapa 2, painel online mínimo.** Criar o app do painel online em uma pasta separada (sugestão: `painel_online/`), com FastAPI + SQLite. Tabelas: `usuarios`, `tokens_api`, `ofertas`, `precos`, `descartados`. Rotas: `POST /api/ingest` (autenticada por token), `GET /api/ofertas`, `POST /api/descartar`, `POST /api/restaurar`. Tela de listagem simples reaproveitando o `frontend/` atual quando possível. Inclua validação com pydantic, limite de tamanho do payload e resposta clara de quantas ofertas foram criadas, atualizadas e ignoradas.

**Etapa 3, login web e tokens.** Login multiusuário com senha em hash, sessão por cookie (`HttpOnly`, `Secure`, `SameSite`), e uma tela para cada usuário gerar e revogar o próprio token de API (o token aparece **uma única vez**, no banco fica só o hash). Criar um comando de linha para criar o primeiro admin (por exemplo `python -m painel_online.criar_admin`). Explicar por que token de API e cookie de sessão são coisas separadas.

**Etapa 4, botão "Enviar ao painel" no painel local.** Em `techdrop_server.py` e no `frontend/`, adicionar o envio das ofertas selecionadas (ou todas as não descartadas) para `PAINEL_URL/api/ingest` usando `PAINEL_TOKEN` do `.env`. Tratar erros com mensagem clara (sem internet, token inválido, servidor fora). Acrescentar `PAINEL_URL` e `PAINEL_TOKEN` ao `.env.example`. O `somente_painel` atual continua protegendo as rotas locais.

**Etapa 5, deploy no VPS Hostinger.** Passo a passo para: criar usuário não-root, firewall (portas 22, 80 e 443), apontar o domínio (registro A), instalar Python, clonar o repositório privado, venv, `pip install` só das dependências do painel online (criar `requirements-painel.txt`, sem Playwright), serviço systemd, Caddy com HTTPS, e backup simples do arquivo SQLite (cron). Os comandos do servidor são Linux, os do meu PC são PowerShell em linha única.

**Etapa 6, guia por PC.** Documentação para quem vai rodar o scraper no próprio computador (ver seção 5).

**Etapa 7, teste de ponta a ponta.** Simular dois PCs enviando o mesmo produto com preços diferentes e provar que: não duplica, o histórico de preços registra os dois, `enviado_por` está correto, token revogado é recusado e rota sem login redireciona. Escrever testes com `pytest` (já existe `tests/`) para ingestão, upsert, autenticação por token e login.

## 5. Entregável principal: o README de compartilhamento

Ao final (e atualizado a cada etapa), gerar o arquivo **`docs/compartilhamento-de-dados.md`** (e um resumo apontando para ele no `README.md` da raiz). Ele é para pessoas que **não conhecem o código**, então deve ser claro, em português do Brasil, sem jargão sem explicação, e com comandos prontos para copiar.

Estrutura obrigatória:

1. **Como funciona (visão geral)**: o que é o painel local, o que é o painel online, o que é o scraper, e por que a coleta roda em cada PC. Incluir o diagrama da seção 3.
2. **O caminho de uma oferta**: do clique em "buscar" no PC até aparecer no painel online (raspar, revisar, enviar, deduplicar, histórico de preço). Em passos numerados.
3. **Para quem administra o painel online**: criar o primeiro admin, criar outros usuários, gerar e revogar tokens, onde fica o banco, como fazer backup, como atualizar o servidor.
4. **Para quem vai rodar o scraper no próprio PC (passo a passo)**:
   - pré-requisitos (Windows, Python, Git) com links oficiais e como verificar a instalação;
   - clonar o repositório;
   - criar o ambiente virtual e instalar as dependências;
   - instalar o Chromium do Playwright;
   - copiar `.env.example` para `.env` e preencher `PAINEL_URL` e `PAINEL_TOKEN`, explicando onde obter o token;
   - iniciar o painel local (`iniciar.bat` e o equivalente em PowerShell);
   - fazer a primeira busca, revisar e clicar em "Enviar ao painel";
   - como conferir no painel online que chegou.
5. **Regras de uso do scraper**: respeitar limites e termos das fontes, não rodar em loop agressivo, não compartilhar o token, o que fazer se uma fonte bloquear (parar, nunca contornar).
6. **Segurança**: nunca commitar `.env`, o que fazer se o token vazar (revogar e gerar outro), por que o login e o token existem.
7. **Solução de problemas**: tabela com sintoma, causa provável e correção (token inválido, sem conexão com o painel, Chromium não instalado, porta 5500 ocupada, oferta não aparece online, oferta duplicada).
8. **Perguntas frequentes** (o envio é automático? posso enviar a mesma oferta duas vezes? quem vê o quê? o que acontece se dois PCs raspam o mesmo produto?).
9. **Glossário** curto (token, upsert, painel local, painel online, scraper, deploy).

Regras do README: cada comando em bloco de código com o terminal indicado (PowerShell no Windows, bash no VPS), um passo por vez, com o resultado esperado logo abaixo de cada comando para a pessoa saber se deu certo. Sem travessão e com emojis mínimos.

## 6. Qualidade e verificação

- Antes de dizer que uma etapa terminou, rode os testes e mostre o resultado.
- Não commitar `.env`, `data/`, `browser_profile/`, `.venv/`, `debug_snapshots/` nem arquivos `.db`. Confira o `.gitignore`.
- Nunca escrever token, senha ou chave real em arquivo versionado. Use `.env.example` com valores de exemplo.
- Ao fim de cada etapa, liste: o que foi feito, como testar, o que ficou para depois.

## 7. Registro do aprendizado

Ao final de cada etapa, escreva um resumo curto e fácil de entender dos conceitos aprendidos (por exemplo: upsert, hash de senha, token Bearer, systemd, proxy reverso) e me entregue em um arquivo `docs/aprendizados/etapa-N.md`, para eu levar depois para o Obsidian.

## 8. Comece agora

Execute apenas a **Etapa 0**: leia o repositório, me devolva o plano e as perguntas que ainda tiver, e aguarde minha confirmação.
