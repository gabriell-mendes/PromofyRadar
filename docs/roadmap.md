# Roadmap

Princípio: **simplicidade → aprendizado → funcionamento → validação → monetização → escala**.

Nada abaixo de "MVP" deve ser implementado antecipadamente.

## MVP (agora)

Objetivo: provar o fluxo mínimo ponta a ponta com dados reais, para uma
única fonte.

- [x] Escolher e validar 1 fonte de dados (API oficial de preferência) —
      Shopee Affiliate Open API, ver `docs/decisao-fonte-de-dados.md`
      (Mercado Livre investigado e descartado por bloqueio de política,
      não é self-service)
- [x] Interface comum a qualquer fonte (`OfferSource`), pra não acoplar o
      resto do sistema a uma fonte específica
- [ ] Coletar produtos de uma consulta simples (ex: "notebook") com
      credenciais reais — código pronto em `app/sources/shopee.py`, falta
      só o Gabriel virar afiliado Shopee e pedir liberação de API (ação
      pessoal, não automatizável — ver `docs/decisao-fonte-de-dados.md`)
- [x] Extrair preço atual + informações básicas (título, preço, link,
      loja, imagem, volume de vendas quando a fonte fornece)
- [x] Normalizar os dados coletados em uma estrutura única (`Product`)
- [ ] Armazenar os produtos coletados (começa simples — pode nem ser
      Postgres ainda) — ainda não existe, é o próximo passo real depois
      de validar a coleta com credenciais de verdade
- [x] Análise básica: alguma regra simples (mediana da busca)
- [x] Deal Score inicial (versão simplificada: mediana da busca + ajuste
      leve por ausência de vendas registradas, quando a fonte informa)
- [x] Filtrar as melhores ofertas encontradas (score, via dashboard)
- [x] Gerar uma mensagem de texto formatada para a oferta
- [x] Revisão manual (dashboard FastAPI, `app/main.py`)

## Depois do MVP

- Validar `app/sources/shopee.py` contra uma resposta real (nomes de
  campo hoje vêm só da documentação pública, nunca confirmados ao vivo)
- Segunda fonte de dados: AliExpress Affiliate API é a candidata natural
  (acesso mais rápido de conseguir que a Shopee, rate limit maior) — ver
  `docs/decisao-fonte-de-dados.md`
- Reavaliar Mercado Livre SE certificação de parceiro de desenvolvedor
  virar possível (contato direto com o Mercado Livre, sem prazo conhecido
  hoje) — código de normalização já pronto em `app/sources/mercadolivre.py`
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

- Múltiplas categorias/fontes simultâneas
- Dashboard/frontend completo (React/TypeScript) — a dashboard atual
  (FastAPI + Jinja2) já cobre a etapa de revisão manual
- Qualquer uso de LLM para "opinar" se uma oferta é boa (decisões
  quantitativas vêm de regras/dados, não de IA)
- Autenticação, multiusuário, multi-tenant
- Filas/mensageria, microserviços
- Qualquer técnica para contornar CAPTCHA, anti-bot, autenticação ou
  restrições de acesso das fontes — Mercado Livre fica de fora do MVP por
  causa desse princípio, não apesar dele
- CI/CD com GitHub Actions (workflows de lint/test útil só quando houver
  deploy automatizado — os testes já existem em `tests/`, rodados
  manualmente com `pytest` por enquanto)
