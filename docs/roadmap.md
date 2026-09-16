# Roadmap

Princípio: **simplicidade → aprendizado → funcionamento → validação → monetização → escala**.

Nada abaixo de "MVP" deve ser implementado antecipadamente.

## MVP (agora)

Objetivo: provar o fluxo mínimo ponta a ponta com dados reais.

- [x] Escolher e validar 1 fonte de dados — API do Mercado Livre bloqueada
      (ver `docs/decisao-fonte-de-dados.md`), Shopee escolhida como fonte
      via API oficial, e depois um pivô consciente para scraping do
      Mercado Livre em vez de esperar aprovação de API
- [x] Interface comum a qualquer fonte (`OfferSource`), pra não acoplar o
      resto do sistema a uma fonte específica
- [x] Coletar produtos de uma consulta simples (ex: "notebook") com dados
      reais — Mercado Livre via scraping (`app/sources/mercadolivre_scraper.py`)
      funciona hoje, sem credencial nenhuma
- [ ] Shopee com credenciais reais — código pronto em `app/sources/shopee.py`,
      falta só o Gabriel virar afiliado e pedir liberação de API (ação
      pessoal, não automatizável — ver `docs/decisao-fonte-de-dados.md`)
- [x] Extrair preço atual + informações básicas (título, preço, link, loja)
- [x] Normalizar os dados coletados em uma estrutura única (`Product`)
- [ ] Armazenar os produtos coletados (começa simples — pode nem ser
      Postgres ainda) — ainda não existe, é o próximo passo real depois
      de validar a coleta do Mercado Livre em mais buscas
- [x] Análise básica: Deal Score relativo à mediana da busca (`app/scoring.py`)
- [x] Lógica de cálculo de desconto, com mínimo configurável
      (`app/filtro.py`, `DESCONTO_MINIMO_PERCENTUAL`)
- [x] Filtrar as melhores ofertas encontradas (desconto mínimo + Deal Score,
      via dashboard)
- [x] Gerar uma mensagem de texto formatada para a oferta
- [x] Revisão manual (dashboard FastAPI, `app/main.py`)

## Depois do MVP

- Validar `app/sources/mercadolivre_scraper.py` contra mais termos de
  busca (os seletores CSS podem quebrar quando o Mercado Livre mudar o
  HTML — ver instruções de validação no `README.md`)
- Validar `app/sources/shopee.py` contra uma resposta real, assim que
  houver credenciais (nomes de campo hoje vêm só da documentação pública,
  nunca confirmados ao vivo)
- Testes automatizados para `mercadolivre_scraper.py` e `filtro.py`
  (hoje sem cobertura — ver seção Testes do `README.md`)
- Terceira fonte de dados: AliExpress Affiliate API é a candidata natural
  (acesso mais rápido de conseguir que a Shopee, rate limit maior) — ver
  `docs/decisao-fonte-de-dados.md`
- Reavaliar Mercado Livre via API oficial SE certificação de parceiro de
  desenvolvedor virar possível — código de normalização já pronto em
  `app/sources/mercadolivre.py` (registrado como `mercadolivre_api`)
- PostgreSQL "de verdade" (schema, migrations)
- Histórico de preços (série temporal por produto) — pré-requisito pra um
  Deal Score que compare com preço justo real, não só com a mediana da
  busca atual
- Identificação de produtos equivalentes entre lojas
- Links de afiliado (geração continua manual por enquanto — decisão já
  registrada)
- Publicação automática no Telegram (bot)
- Métricas de cliques/vendas
- Containerização com Docker
- Deploy

## Não é prioridade agora (evitar overengineering)

- Múltiplas fontes rodando ao mesmo tempo numa busca só (hoje é uma fonte
  por vez, via `OFFER_SOURCE`)
- Múltiplas categorias/fontes simultâneas
- Dashboard/frontend completo (React/TypeScript) — a dashboard atual
  (FastAPI + Jinja2) já cobre a etapa de revisão manual
- Qualquer uso de LLM para "opinar" se uma oferta é boa (decisões
  quantitativas vêm de regras/dados, não de IA)
- Autenticação, multiusuário, multi-tenant
- Filas/mensageria, microserviços
- Qualquer técnica para contornar CAPTCHA, anti-bot ou autenticação —
  o scraping do Mercado Livre simula uma visita normal e para se detectar
  bloqueio/verificação, nunca tenta contornar
- CI/CD com GitHub Actions (workflows de lint/test útil só quando houver
  deploy automatizado — os testes já existem em `tests/`, rodados
  manualmente com `pytest` por enquanto)
