# Grupo de Ofertas

Ferramenta pessoal para encontrar automaticamente boas ofertas de produtos e
divulgá-las em canais de Deal Alerts (ex: Telegram), monetizando via
programas de afiliados.

## Objetivo

Não é um SaaS comercial. É uma ferramenta para uso próprio que também serve
como projeto de aprendizado prático de Python, HTTP/APIs, scraping
responsável, banco de dados e arquitetura de backend.

O sistema deve identificar ofertas *realmente* boas — com base em histórico
de preços e dados objetivos — e não apenas em "desconto anunciado pela loja".

## Como funciona (visão geral)

```
consulta → busca de produtos → coleta de dados → normalização
  → armazenamento → histórico de preços → Deal Score
  → filtro das melhores ofertas → revisão manual
  → geração de mensagem → publicação
```

Nem tudo isso existe ainda — veja o status abaixo e o roadmap detalhado em
[`docs/roadmap.md`](docs/roadmap.md).

## Stack

- Python (requests/httpx, Playwright quando necessário, pandas quando fizer sentido)
- PostgreSQL
- FastAPI (mais adiante)
- Telegram Bot API (mais adiante)
- Docker/Docker Compose (mais adiante)

## Status atual

🚧 Ainda não há coleta funcionando. Existe uma dashboard de revisão manual
(`app/`) rodando com dados fictícios (`app/mock_data.py`), só para validar a
tela da etapa "revisão manual" antes de plugar o collector real.

## Como rodar

### Dashboard de revisão manual

```
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra http://127.0.0.1:8000 — vai aparecer uma lista de ofertas fictícias
com score, motivo e a mensagem pronta para copiar/colar no Telegram.

Isso ainda **não é** o dashboard/frontend completo mencionado como fora de
escopo em `docs/roadmap.md` — é só a tela mínima para a etapa de revisão
manual que já fazia parte do MVP, sem React/build tooling, fácil de trocar
depois.

## Documentação

- [`docs/architecture.md`](docs/architecture.md) — arquitetura atual e decisões técnicas
- [`docs/roadmap.md`](docs/roadmap.md) — o que é MVP, o que vem depois, o que NÃO é prioridade agora
- [`docs/data-model.md`](docs/data-model.md) — modelo de dados (produto, oferta, preço, loja)
