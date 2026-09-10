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

🚧 Projeto em setup inicial. Ainda não há coleta funcionando.

## Como rodar

_(será preenchido conforme o MVP for tomando forma)_

## Documentação

- [`docs/architecture.md`](docs/architecture.md) — arquitetura atual e decisões técnicas
- [`docs/roadmap.md`](docs/roadmap.md) — o que é MVP, o que vem depois, o que NÃO é prioridade agora
- [`docs/data-model.md`](docs/data-model.md) — modelo de dados (produto, oferta, preço, loja)
