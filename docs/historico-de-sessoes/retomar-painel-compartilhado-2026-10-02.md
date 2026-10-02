# Retomada: painel TechDrop compartilhado

Sou o Gabriel. Projeto Grupo de Ofertas (deal alerts + afiliados), pasta `grupo-de-ofertas` na raiz. Isto é a continuação de uma sessão anterior do Claude Code onde já defini o plano e andei a Etapa 0 e parte da Etapa 1. Este prompt tem todo o contexto que você precisa, não existe histórico de conversa anterior para consultar.

## 1. Objetivo geral

Evoluir o painel local (`techdrop_server.py`, FastAPI, serve `frontend/` e roda os scrapers) para um modelo com painel online compartilhado:

- Cada pessoa roda o painel e o scraper no próprio PC (IP e navegador próprios).
- Existe um painel online num VPS da Hostinger (KVM), que todos os administradores acessam.
- No painel local, a pessoa revisa as ofertas raspadas e clica em "Enviar ao painel". As aprovadas vão para o painel online, onde todos os admins veem tudo junto.
- O VPS não roda scraper nem usa Playwright. Só recebe, guarda, deduplica e exibe.

## 2. Princípios do projeto (obrigatórios, valem para toda a conversa)

- Antes de implementar cada etapa, explique em poucas linhas o objetivo, os conceitos necessários e onde ela se encaixa na arquitetura.
- Trabalhe em etapas pequenas. Pare ao fim de cada etapa, mostre o que mudou, como testar, e espere eu confirmar antes de seguir.
- Prefira soluções simples e compreensíveis. Sem overengineering: nada de Redis, Celery, microserviços, OAuth ou permissões por perfil neste momento.
- Quando fizer sentido, deixe uma parte pequena para eu tentar implementar (ex: um modelo pydantic ou uma função), e revise meu código depois, explicando os erros.
- Diferencie sempre o que é MVP, o que é melhoria futura e o que é desnecessário agora.
- Valide cada etapa com dados reais (um `ofertas.json` verdadeiro) antes de avançar.
- Decisões quantitativas (Deal Score etc) continuam baseadas em dados e regras explícitas, nunca LLM opinando.
- Coleta: respeitar termos de uso e limites das fontes. Nunca propor ou implementar técnicas para burlar CAPTCHA, autenticação ou anti-bot. Se uma fonte bloquear, o caminho é API oficial ou reduzir frequência, nunca contornar.
- Comandos de terminal: PowerShell em linha única, comandos separados por ponto e vírgula (nunca `&&`), diretos, explicação mínima.
- Escrita: sem travessão (use vírgula, dois-pontos ou espaço). Emojis só quando servirem de identificação visual rápida.

## 3. Arquitetura real do projeto (já verificada, não é a dos docs antigos)

`techdrop_server.py` (FastAPI) serve `frontend/` e dispara `scraperd.py` / `scraper_categoria.py` / `scraper_ofertas.py` como subprocesso. O scraper grava em `frontend/data/_ultima_busca.json`, o servidor funde isso em `frontend/data/ofertas.json` e `descartados.json`, deduplicando pelo campo `link`. Deal Score vem de `deal_score.py` + `historico.py` (SQLite local em `data/historico_precos.db`, um preço por produto por dia, por PC) + `pontuacao.py`. `categorias_ml.py` e `ofertas_abas.py` alimentam os botões do painel.

**Importante:** `docs/architecture.md`, `docs/data-model.md`, `docs/roadmap.md` e `.env.example` descrevem uma versão anterior e abandonada do projeto (pasta `app/`: `Product`, `OfferSource`, Shopee API). Decisão já tomada: **deixar esses quatro arquivos intocados por agora**, não usá-los como referência de arquitetura. Quem documenta a realidade atual é `docs/estrutura-do-projeto.md` e `docs/deal-score.md`.

## 4. Decisões já fechadas (não reabrir sem motivo forte)

| Ponto | Decisão |
|---|---|
| Armazenamento no VPS | SQLite (não JSON), por causa de escrita concorrente de vários PCs |
| Produto repetido | Upsert pela chave única (loja + id_produto) |
| Preços | Cada envio gera uma linha em `precos` (produto, preço, data, enviado_por), formando histórico. Não é "um por dia" como o histórico local, é por envio mesmo |
| Autoria | Campo `enviado_por` em cada oferta e em cada preço, preenchido pelo servidor a partir do token autenticado, nunca um campo que o cliente manda (evita um PC se passar por outro usuário) |
| Descartados | Ficam no VPS e são compartilhados entre todos os admins |
| Acesso de pessoas | Login usuário/senha (hash com bcrypt), sessão por cookie |
| Acesso dos PCs | Token de API por usuário, header `Authorization: Bearer`, guardado com hash no banco e revogável |
| Envio | Manual, por botão no painel local (revisão antes de enviar). Envio automático fica para depois |
| Hospedagem | VPS Ubuntu, uvicorn em 127.0.0.1 via systemd, Caddy na frente com HTTPS automático. Sem Docker por enquanto |
| `id_produto` | Não é enviado pelo cliente. O servidor deriva de `url` usando `chave_produto()` (já existe em `historico.py`, regex do código `MLB...`). Mais simples e evita confiar num campo derivado que o cliente poderia mandar errado |
| `.gitignore` da raiz | Já corrigido: agora ignora `data/` e `*.db` (antes os bancos SQLite ficavam sem proteção contra `git add -A`) |

Fora do MVP: OAuth, recuperação de senha por e-mail, filas, permissões por perfil, sincronização do VPS de volta para os PCs, envio automático, dashboard avançado.

## 5. Contrato da Etapa 1 (`OfertaIn`), já definido

Baseado em dados reais de `frontend/data/ofertas.json` (42 ofertas checadas). A chave de upsert é `(loja, id_produto)`, com `id_produto = chave_produto(url)`.

| Campo | Tipo | Obrigatório | Vem de | Observação |
|---|---|---|---|---|
| `loja` | str | sim | fixo `"mercadolivre"` por enquanto | string livre, não enum, para permitir 2ª loja no futuro |
| `url` | str | sim | `link` do scraper | usada para derivar `id_produto`, nunca enviada já processada |
| `titulo` | str | sim | `title` | |
| `preco` | float (> 0) | sim | `price` | |
| `preco_original` | float \| None | não | `old_price` | pode vir igual ao `preco` quando não há desconto real |
| `desconto` | float \| None | não | `discount` | informativo, não revalidado contra preço/preço original no MVP |
| `parcelamento` | str \| None | não | `installment` | só exibição |
| `imagem` | str \| None | não | `image` | |
| `categoria` | str \| None | não | `category` | só presente em coletas por categoria/aba |
| `deal_score` | int \| None | não | `deal_score` | calculado no PC de origem, sobre o histórico daquele PC. Painel online só guarda o último valor recebido, não recalcula (recalcular de forma central é melhoria futura) |
| `deal_confianca` | str \| None | não | `deal_confianca` | |
| `deal_motivos` | list[str] | não (default `[]`) | `deal_motivos` | |
| `deal_flags` | list[str] | não (default `[]`) | `deal_flags` | |
| `coletado_em` | datetime \| None | não | novo campo, preenchido pelo `techdrop_server.py` no momento do envio (Etapa 4) | se vazio, quem recebe usa o horário de recebimento |

De propósito fora do contrato: `id_produto` (derivado de `url` por quem recebe) e `enviado_por` (vem do token de autenticação, Etapa 3).

## 6. Estado atual dos arquivos

- `painel_online/__init__.py`: criado, vazio (só marca o pacote).
- `painel_online/schemas.py`: existe só com um comentário TODO listando os campos acima. **A classe `OfertaIn` (pydantic.BaseModel) ainda não foi escrita.**
- `painel_online/upsert.py`: existe só com um comentário TODO. **A função que decide "novo" ou "atualizacao" ainda não foi escrita.** Ela deve importar `chave_produto` de `historico.py` (`from historico import chave_produto`, está na raiz do projeto) para calcular `id_produto = chave_produto(oferta.url)`.
- `.gitignore` da raiz: já tem `data/` e `*.db` adicionados.
- Nada mais do projeto foi alterado por mim além disso.

## 7. O que falta (continuar exatamente daqui)

**Etapa 1 (em andamento):** eu (Gabriel) vou escrever `OfertaIn` em `painel_online/schemas.py` e a função de decisão em `painel_online/upsert.py`. Quando eu avisar que terminei, revise meu código, explique erros se houver, e valide com o exemplo real: o link `https://www.mercadolivre.com.br/.../p/MLB25171538?pdp_filters=...` deve gerar `id_produto = "MLB25171538"`, e dois envios desse mesmo link (mesmo com query string diferente) devem cair na mesma chave e resultar em `"atualizacao"` na segunda vez.

**Etapa 2, painel online mínimo.** Criar o app em `painel_online/` com FastAPI + SQLite. Tabelas: `usuarios`, `tokens_api`, `ofertas`, `precos`, `descartados`. Rotas: `POST /api/ingest` (autenticada por token), `GET /api/ofertas`, `POST /api/descartar`, `POST /api/restaurar`. Tela de listagem simples reaproveitando o `frontend/` atual quando possível. Validação com pydantic, limite de tamanho do payload, resposta clara de quantas ofertas foram criadas/atualizadas/ignoradas.

**Etapa 3, login web e tokens.** Login multiusuário com senha em hash, sessão por cookie (HttpOnly, Secure, SameSite), tela para cada usuário gerar e revogar o próprio token de API (aparece uma única vez, no banco só o hash). Comando de linha para criar o primeiro admin (`python -m painel_online.criar_admin`). Explicar por que token de API e cookie de sessão são coisas separadas.

**Etapa 4, botão "Enviar ao painel" no painel local.** Em `techdrop_server.py` e no `frontend/`, enviar as ofertas selecionadas (ou todas as não descartadas) para `PAINEL_URL/api/ingest` usando `PAINEL_TOKEN` do `.env`. Tratar erros com mensagem clara (sem internet, token inválido, servidor fora). Acrescentar `PAINEL_URL` e `PAINEL_TOKEN` ao `.env.example` (sem mexer no resto do arquivo, que é antigo). `somente_painel` continua protegendo as rotas locais.

**Etapa 5, deploy no VPS Hostinger.** Usuário não-root, firewall (22/80/443), domínio (registro A), Python, clone do repositório privado, venv, `requirements-painel.txt` (sem Playwright), systemd, Caddy com HTTPS, backup do SQLite via cron. Comandos do servidor são Linux, os do meu PC são PowerShell em linha única.

**Etapa 6, guia por PC.** Documentação para quem vai rodar o scraper no próprio computador (ver seção 8 abaixo).

**Etapa 7, teste de ponta a ponta.** Simular dois PCs enviando o mesmo produto com preços diferentes: não duplica, histórico de preços registra os dois, `enviado_por` correto, token revogado é recusado, rota sem login redireciona. Testes com pytest (já existe `tests/`).

## 8. Entregável: `docs/compartilhamento-de-dados.md`

Ao final de cada etapa, atualizar este arquivo (e um resumo apontando pra ele no `README.md` da raiz). Para pessoas que não conhecem o código, português do Brasil, sem jargão sem explicação, comandos prontos para copiar. Estrutura obrigatória: visão geral com o diagrama (PC local -> HTTPS POST /api/ingest com Bearer token -> painel online -> login cookie para os admins), o caminho de uma oferta passo a passo, administração do painel online, guia completo para quem roda o scraper no próprio PC (pré-requisitos, clonar, venv, Playwright, `.env`, iniciar, buscar, revisar, enviar, conferir), regras de uso do scraper, segurança (nunca commitar `.env`, o que fazer se o token vazar), solução de problemas (tabela sintoma/causa/correção), perguntas frequentes, glossário.

## 9. Qualidade e verificação

- Antes de dizer que uma etapa terminou, rode os testes e mostre o resultado.
- Não commitar `.env`, `data/`, `browser_profile/`, `.venv/`, `debug_snapshots/` nem arquivos `.db`.
- Nunca escrever token, senha ou chave real em arquivo versionado. Use `.env.example` com valores de exemplo.
- Ao fim de cada etapa, liste: o que foi feito, como testar, o que ficou para depois.
- Ao final de cada etapa, escreva um resumo curto dos conceitos aprendidos em `docs/aprendizados/etapa-N.md` (para eu levar ao Obsidian).

## 10. Comece agora

Continue a Etapa 1 de onde parou: espere eu mostrar o `OfertaIn` e a função de upsert que vou escrever em `painel_online/schemas.py` e `painel_online/upsert.py`, revise com calma, explique qualquer erro, e só depois disso valide seguir para a Etapa 2.
