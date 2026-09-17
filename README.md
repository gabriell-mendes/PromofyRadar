# Grupo de Ofertas

Ferramenta pessoal para encontrar automaticamente boas ofertas de produtos e
divulgá-las em canais de Deal Alerts (ex: Telegram), monetizando via
programas de afiliados.

## Objetivo

Não é um SaaS comercial. É uma ferramenta para uso próprio que também serve
como projeto de aprendizado prático de Python, scraping, APIs, banco de
dados e arquitetura de backend.

O sistema deve identificar ofertas *realmente* boas — com base em dados
objetivos coletados — e não apenas em "desconto anunciado pela loja".

## Como funciona hoje

```
consulta (ex: "notebook")
    │
    ▼
fonte de ofertas (busca + normalização)   ← app/sources/*.py, atrás da
    │                                        interface comum OfferSource
    ▼
Deal Score (relativo à mediana da busca)  ← app/scoring.py
    │
    ▼
filtro de desconto mínimo (absoluto)      ← app/filtro.py
    │
    ▼
geração de mensagem                       ← app/message.py
    │
    ▼
revisão manual (dashboard)                ← app/main.py — você decide o
                                             que publicar; link de afiliado
                                             é gerado por você, fora do
                                             código
```

Etapas que ainda não existem (ver [`docs/roadmap.md`](docs/roadmap.md)):
armazenamento/histórico de preços, publicação automática no Telegram,
métricas de cliques/vendas.

## Status atual

**Mercado Livre é a fonte padrão**, via scraping real com Playwright
(`app/sources/mercadolivre_scraper.py`) — funciona sem nenhuma credencial.
A API oficial do Mercado Livre foi investigada e descartada por bloqueio
de política do próprio backend deles (não é algo contornável de forma
legítima); esse código antigo continua no repo, desativado, como
`mercadolivre_api` (ver [`docs/decisao-fonte-de-dados.md`](docs/decisao-fonte-de-dados.md)).

**Shopee Affiliate Open API** (`app/sources/shopee.py`) está implementada
e testada com mocks, mas **ainda sem credenciais reais** — depende de
Gabriel virar afiliado aprovado e pedir liberação de API. Sem isso, ela
levanta erro de configuração em vez de dados.

A dashboard de revisão manual (`app/`) já roda o pipeline real de ponta a
ponta contra o Mercado Livre: busca → Deal Score → filtro de desconto →
mensagem pronta pra copiar/colar.

⚠️ Scraping de página de busca é uma decisão consciente, não isenta de
risco: sites mudam HTML com frequência (quebra seletor) e têm termos de
uso próprios. Este projeto não usa nenhuma técnica de evasão (sem burlar
CAPTCHA, sem mascarar automação, sem IP rotation) — se uma página de
verificação/bloqueio for detectada, a coleta para e reporta erro, não
tenta contornar.

## Como rodar

### 1. Instalar dependências

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

O `chromium` do Playwright é obrigatório: é o navegador que a fonte do
Mercado Livre usa pra simular uma visita real à página de busca.

### 2. Configurar

```powershell
cp .env.example .env
```

Não precisa preencher nada pra usar o Mercado Livre (fonte padrão). As
variáveis relevantes, todas opcionais:

| Variável | Pra quê | Padrão |
|---|---|---|
| `OFFER_SOURCE` | qual fonte usar: `mercadolivre`, `shopee` ou `mercadolivre_api` (histórica, sempre erro) | `mercadolivre` |
| `DESCONTO_MINIMO_PERCENTUAL` | desconto mínimo (%) pra uma oferta aparecer na revisão | `30` |
| `MERCADOLIVRE_MIN_INTERVAL_SECONDS` | intervalo mínimo entre buscas no Mercado Livre | `2.0` |
| `SHOPEE_APP_ID` / `SHOPEE_APP_SECRET` | credenciais da Shopee, só necessárias se `OFFER_SOURCE=shopee` | — |

### 3. Rodar a dashboard

```powershell
uvicorn app.main:app --reload
```

Abra http://127.0.0.1:8000 — aparece uma lista de ofertas reais do
Mercado Livre, com score, motivo do score, e a mensagem pronta.

Isso **não é** o dashboard/frontend completo mencionado como fora de
escopo em `docs/roadmap.md` — é a tela mínima da etapa de revisão manual,
sem React/build tooling, fácil de trocar depois.

### Mudando o que buscar e o desconto mínimo

Duas formas, dependendo se você quer mudar só pra essa busca ou deixar um
padrão novo pra sempre.

**Na própria página**, sem editar nada: tem um campo de texto (o que
buscar) e um campo numérico (desconto mínimo em %) ao lado do botão
"Buscar". Muda os dois e busca de novo, sem reiniciar o servidor.

**Direto pela URL**, do mesmo jeito, útil se você quer salvar um link ou
testar rápido no terminal/Postman:

```
http://127.0.0.1:8000/?q=ssd+nvme&desconto_min=50
```

`q` é o termo de busca (qualquer coisa: "notebook", "monitor 144hz",
"placa de vídeo amd"), `desconto_min` é o corte de desconto em %. Os dois
são opcionais — se não passar nenhum, usa os padrões (`notebook` e `30`).

**Pra mudar o padrão permanentemente**, sem precisar passar na URL toda
vez: edite `DESCONTO_MINIMO_PERCENTUAL` no `.env` (ver tabela de variáveis
acima) e reinicie o `uvicorn`. Não existe hoje um jeito de mudar o termo
de busca padrão fora do código — ele é a constante `QUERY_PADRAO` em
`app/main.py` — mas como o campo na página já cobre "buscar outra coisa"
sem reiniciar nada, isso raramente é necessário.

### 4. Validar o scraper com dado real

Sites mudam HTML com frequência — antes de confiar nos resultados (ou
depois de qualquer suspeita de que algo parou de vir preenchido), rode a
fonte isolada, fora da dashboard:

```powershell
python -m app.sources.mercadolivre_scraper "notebook" --headed --verbose
```

`--headed` abre o navegador visível, `--verbose` mostra os logs. Mostra o
primeiro item cru extraído (antes de normalizar) e a lista já normalizada.
Se um campo vier `None`, é sinal de que o seletor CSS correspondente
mudou — ele fica centralizado em `SELECTORS`, no topo do arquivo.

### 5. Testes

```powershell
pip install -r requirements-dev.txt
pytest
```

Cobrem hoje: comportamento comum a qualquer fonte (`OfferSource`,
descarte de item inválido/duplicado), a fonte Shopee (resposta válida/
vazia/erro HTTP/timeout/rate limit/dados incompletos), a fonte Mercado
Livre antiga via API (`mercadolivre_api`, permanece desativada, sem
chamada de rede), o Deal Score, e a geração de mensagem.

**Gap conhecido, ainda não preenchido:** não existe teste automatizado
pra `app/sources/mercadolivre_scraper.py` (scraping real, mais difícil de
testar sem mockar Playwright/HTML) nem pra `app/filtro.py` (mais simples
de cobrir — é só matemática sobre `Product`).

## Estrutura do projeto

```
app/
  models.py               Product e ReviewItem — modelo de dados comum
  config.py                get_source(): escolhe a fonte por OFFER_SOURCE
  scoring.py                Deal Score (relativo à mediana da própria busca)
  filtro.py                 filtro de desconto mínimo (absoluto, vs. preço "de")
  message.py                monta o texto pronto pra publicação
  main.py                    dashboard FastAPI (rota única de revisão manual)
  sources/
    base.py                  OfferSource — interface comum a qualquer fonte
    mercadolivre_scraper.py  fonte ATIVA: scraping (Playwright + BeautifulSoup)
    mercadolivre_page.py     utilitário isolado: inspeciona 1 URL de produto
    mercadolivre.py          fonte histórica via API oficial (desativada)
    shopee.py                fonte via API oficial (precisa credenciais)
templates/review.html      página única da dashboard (Jinja2)
static/style.css            estilo da dashboard
tests/                       pytest — ver seção Testes acima
docs/                         decisões e arquitetura, ver abaixo
```

Regra que vale pra qualquer arquivo em `app/sources/`: só ele conhece o
formato da fonte (nomes de campo, seletores CSS, autenticação). Todo o
resto do projeto (`scoring.py`, `filtro.py`, `message.py`, `main.py`) só
conhece `Product` — trocar ou somar fonte não deveria exigir tocar neles.

## Documentação

- [`docs/decisao-fonte-de-dados.md`](docs/decisao-fonte-de-dados.md) —
  por que a API do Mercado Livre foi descartada, comparação com as
  alternativas investigadas (Shopee, AliExpress, Amazon...), e o pivô
  posterior para scraping
- [`docs/architecture.md`](docs/architecture.md) — arquitetura atual e
  decisões técnicas
- [`docs/roadmap.md`](docs/roadmap.md) — o que é MVP, o que já foi feito,
  o que vem depois, o que NÃO é prioridade agora
- [`docs/data-model.md`](docs/data-model.md) — modelo de dados (`Product`)
