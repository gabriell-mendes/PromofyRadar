# Grupo de Ofertas

Ferramenta pessoal para encontrar automaticamente boas ofertas de produtos e
divulgá-las em canais de Deal Alerts (ex: Telegram), monetizando via
programas de afiliados.

## Objetivo

Não é um SaaS comercial. É uma ferramenta para uso próprio que também serve
como projeto de aprendizado prático de Python, HTTP/APIs, banco de dados e
arquitetura de backend.

O sistema deve identificar ofertas *realmente* boas — com base em histórico
de preços e dados objetivos — e não apenas em "desconto anunciado pela loja".

## Como funciona (visão geral)

```
consulta → fonte de ofertas (busca + normalização) → armazenamento
  → histórico de preços → Deal Score → filtro das melhores ofertas
  → revisão manual → geração de mensagem → publicação
```

Nem tudo isso existe ainda — veja o status abaixo, a decisão de fonte de
dados em [`docs/decisao-fonte-de-dados.md`](docs/decisao-fonte-de-dados.md)
e o roadmap detalhado em [`docs/roadmap.md`](docs/roadmap.md).

## Stack

- Python (requests, FastAPI, python-dotenv)
- PostgreSQL (mais adiante)
- Telegram Bot API (mais adiante)
- Docker/Docker Compose (mais adiante)

## Status atual

🚧 Fonte de dados escolhida e implementada (Shopee Affiliate Open API),
mas ainda sem credenciais reais configuradas — ver
[`docs/decisao-fonte-de-dados.md`](docs/decisao-fonte-de-dados.md) para os
próximos passos. Existe uma dashboard de revisão manual (`app/`) que já
usa o pipeline real (fonte → Deal Score → mensagem); sem credenciais
configuradas, ela mostra o erro de configuração em vez de dados —
`app/mock_data.py` continua disponível como referência/fallback visual.

Mercado Livre foi investigado e descartado como fonte do MVP (bloqueio de
política do próprio Mercado Livre, não algo contornável de forma legítima)
— fica registrado como possibilidade futura em
[`docs/decisao-fonte-de-dados.md`](docs/decisao-fonte-de-dados.md).

## Como rodar

### Configuração

```
cp .env.example .env
```

Preencha `SHOPEE_APP_ID` e `SHOPEE_APP_SECRET` no `.env` (exige virar
afiliado Shopee aprovado e pedir liberação de API — ver
[`docs/decisao-fonte-de-dados.md`](docs/decisao-fonte-de-dados.md)). Sem
isso, a dashboard sobe normalmente mas mostra erro ao buscar.

### Dashboard de revisão manual

```
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra http://127.0.0.1:8000 — vai aparecer uma lista de ofertas com score,
motivo e a mensagem pronta para copiar/colar no Telegram.

Isso ainda **não é** o dashboard/frontend completo mencionado como fora de
escopo em `docs/roadmap.md` — é só a tela mínima para a etapa de revisão
manual que já fazia parte do MVP, sem React/build tooling, fácil de trocar
depois.

### Testes

```
pip install -r requirements-dev.txt
pytest
```

Cobrem: comportamento comum a qualquer fonte (descarte de item inválido/
duplicado), a fonte Shopee (resposta válida/vazia/erro HTTP/timeout/rate
limit/dados incompletos), a fonte Mercado Livre (permanece desativada, sem
chamada de rede), o Deal Score, e a geração de mensagem.

## Documentação

- [`docs/decisao-fonte-de-dados.md`](docs/decisao-fonte-de-dados.md) —
  por que Mercado Livre foi descartado, alternativas comparadas, e por
  que a Shopee foi escolhida pro MVP
- [`docs/architecture.md`](docs/architecture.md) — arquitetura atual e decisões técnicas
- [`docs/roadmap.md`](docs/roadmap.md) — o que é MVP, o que vem depois, o que NÃO é prioridade agora
- [`docs/data-model.md`](docs/data-model.md) — modelo de dados (produto, oferta, preço, loja)
