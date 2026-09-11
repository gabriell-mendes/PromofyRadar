# Roadmap

Princípio: **simplicidade → aprendizado → funcionamento → validação → monetização → escala**.

Nada abaixo de "MVP" deve ser implementado antecipadamente.

## MVP (agora)

Objetivo: provar o fluxo mínimo ponta a ponta com dados reais, para uma
única fonte.

- [ ] Escolher e validar 1 fonte de dados (API oficial de preferência)
- [ ] Coletar produtos de uma consulta simples (ex: "notebook")
- [ ] Extrair preço atual + informações básicas (título, preço, link, loja)
- [ ] Normalizar os dados coletados em uma estrutura única (`Product`)
- [ ] Armazenar os produtos coletados (começa simples — pode nem ser Postgres ainda)
- [ ] Análise básica: alguma regra simples (não precisa ser o Deal Score completo)
- [ ] Deal Score inicial (versão simplificada, com poucos fatores)
- [ ] Filtrar as melhores ofertas encontradas
- [ ] Gerar uma mensagem de texto formatada para a oferta
- [ ] Revisão manual (eu decido se publico ou não)

## Depois do MVP

- Segunda fonte de dados
- PostgreSQL "de verdade" (schema, migrations)
- Histórico de preços (série temporal por produto)
- Identificação de produtos equivalentes entre lojas
- Links de afiliado
- Publicação automática no Telegram (bot)
- Métricas de cliques/vendas
- API com FastAPI
- Containerização com Docker
- Deploy

## Não é prioridade agora (evitar overengineering)

- Múltiplas categorias/fontes simultâneas
- Dashboard/frontend (React/TypeScript)
- Qualquer uso de LLM para "opinar" se uma oferta é boa (decisões
  quantitativas vêm de regras/dados, não de IA)
- Autenticação, multiusuário, multi-tenant
- Filas/mensageria, microserviços
- Qualquer técnica para contornar CAPTCHA, anti-bot, autenticação ou
  restrições de acesso das fontes
- CI/CD com GitHub Actions (workflows de lint/test útil só quando houver testes e deploy automatizado)
