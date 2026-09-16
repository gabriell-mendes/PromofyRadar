# Decisão: fonte de dados do MVP

Data: 2026-09-14 (ver seção F para o pivô posterior, de 2026-09-15/16,
que é a decisão que vale hoje — as seções abaixo continuam sendo o
registro histórico de como se chegou até ali, e a comparação entre Shopee
e AliExpress nelas continua válida)

## A. Diagnóstico

O MVP precisava de UMA fonte real de produtos/ofertas pra alimentar o
pipeline (busca → normalização → Deal Score → mensagem → revisão manual).
Mercado Livre era a fonte planejada originalmente, por ser o maior
marketplace do Brasil e ter (na teoria) uma API pública de busca.

Na prática, `api.mercadolibre.com/sites/MLB/search` retorna sempre
`403 Forbidden`, com o corpo `{"message":"forbidden","error":"forbidden","status":403,"cause":[]}`
e o código interno `PA_UNAUTHORIZED_RESULT_FROM_POLICIES` — um bloqueio do
"PolicyAgent" do próprio backend do Mercado Livre.

Isso foi investigado de forma extensa antes de descartar a fonte, especificamente pra
não confundir "bloqueio de política" com "bug de configuração que um outro
header resolveria":

- testado com script Python (`requests`) puro, sem autenticação;
- testado com token OAuth válido (o mesmo token funciona normalmente em
  `/users/me`, `/orders` — ou seja, não é token inválido nem escopo errado);
- testado em endpoints diferentes: `/sites/MLB` (metadado público básico,
  historicamente sempre aberto), `/sites/MLB/categories`, `/items/{id}` e
  `/sites/MLB/search` — todos com o mesmo erro;
- testado num Chrome real (fingerprint TLS diferente de um script) via
  Claude in Chrome — mesmo 403, mesmo JSON de erro;
- confirmado em relatos de outros desenvolvedores independentes, em datas
  e contas diferentes, no Reclame Aqui, com o mesmo sintoma;
- a resposta oficial do Mercado Livre a uma dessas reclamações direciona o
  caso para "canais de suporte especializados para desenvolvedores e
  parceiros certificados" — ou seja, existe uma trilha de acesso
  legítimo, mas não é self-service nem documentada publicamente, e não tem
  prazo ou critério de aprovação conhecidos;
- o programa de afiliados do próprio Mercado Livre não expõe API de busca,
  só geração manual de link (confirmado em fórum oficial do Reclame Aqui:
  "Programa de afiliados do Mercado Livre não tem uma API");
- o conector Mercado Livre disponível via Kondado usa a API de VENDEDOR
  (`/users/{id}/items`), que só lista os anúncios da própria conta
  autorizada — não serve pra buscar ofertas de terceiros no marketplace.

Conclusão: não é um problema de header, User-Agent, IP ou fingerprint —
logo, não é algo que se resolve com proxy, rotação de IP, outro cliente
HTTP ou stealth de navegador (e o projeto não faria isso mesmo que
resolvesse). É um bloqueio de política, com uma trilha de acesso oficial
não self-service. **Mercado Livre não é uma fonte viável para o MVP.**

## B. Alternativas investigadas

| Fonte | API de busca oficial | Requisito de acesso | Rate limit / custo | Frete relevante p/ BR | Veredito |
|---|---|---|---|---|---|
| **Mercado Livre** | Sim, mas bloqueada (`PA_UNAUTHORIZED_RESULT_FROM_POLICIES`) pra terceiros não certificados | Certificação de parceiro não documentada publicamente, sem prazo/critério conhecido | N/A (bloqueado) | Sim (líder no Brasil) | ❌ Roadmap (não MVP) |
| **Shopee Affiliate Open API (BR)** | Sim — GraphQL, `productOfferV2` (busca por palavra-chave/categoria/loja, ordena por preço/vendas/comissão) | Virar afiliado aprovado + pedir liberação de API pelo painel (self-service, mas com espera — resposta em até ~2 semanas) | Grátis (comissão sobre venda); rate limit existe (erro 10030) | Sim (forte no Brasil, entrega local) | ✅ **Escolhida pro MVP** |
| **AliExpress Affiliate API** | Sim — REST, `aliexpress.affiliate.product.query` e afins | Cadastro no programa de afiliados (revisão manual) + app no Open Platform tipo "Affiliate API" (aprovação em ~2 dias úteis) | Grátis; 5.000 requisições/dia documentado | Não (frete internacional, mais lento) | 🟡 Candidata a 2ª fonte |
| **Amazon (PA-API 5 → Creators API)** | Só depois de qualificado | Exige **10 vendas qualificadas nos últimos 30 dias** pra liberar a API — ou seja, precisa vender pela Amazon ANTES de poder buscar produtos pela API | Grátis após qualificação | Sim | ❌ Inviável pro MVP (dependência circular: precisa de vendas pra ter API, precisa da API pra gerar as ofertas que gerariam vendas) |
| **Awin** | API de produto existe, mas aprovação é por loja/anunciante individual dentro da rede, não uma API geral de marketplace | Alto esforço (aprovar loja por loja) | Varia por anunciante | Depende da loja aprovada | ❌ Não serve pro MVP (esforço não compensa pra uma fonte única) |
| **Lomadee** | Não — só link manual e feed XML por loja | — | — | — | ❌ Sem API de busca |
| **Kabum** | Não tem API oficial, só scrapers de terceiros não-oficiais | — | — | — | ❌ Descartada (projeto não usa scraping não-autorizado) |

Critérios de peso alto (legalidade, estabilidade, dados de preço/
disponibilidade, possibilidade de afiliado, custo) eliminam Awin, Lomadee,
Kabum e Amazon de cara. Entre Shopee e AliExpress — as duas únicas com API
de busca oficial, documentada, e caminho de aprovação individual —, a
escolha final considerou o público-alvo do projeto: divulgar **boas
ofertas para o Brasil**. Frete internacional lento da AliExpress reduz a
credibilidade percebida de uma "oferta boa" divulgada num canal de Deal
Alerts — quem recebe uma oferta espera poder comprar e receber rápido. A
Shopee tem forte presença e entrega local no Brasil, além de já fornecer
volume de vendas (`sales`) e faixa de preço por item — dado extra que o
Mercado Livre nunca chegou a fornecer de verdade (bloqueado antes de
qualquer validação) e que a AliExpress exigiria descobrir na prática.

## C. Decisão

```text
MERCADO LIVRE = ROADMAP
MVP = SHOPEE AFFILIATE OPEN API
```

- **Mecanismo:** GraphQL, `POST https://open-api.affiliate.shopee.com.br/graphql`,
  operação `productOfferV2`, autenticação por assinatura SHA-256 (sem
  OAuth) — ver `app/sources/shopee.py`.
- **Documentação:** https://www.affiliateshopee.com.br/documentacao
  (documentação oficial da Shopee Brasil pra afiliados).
- **Requisitos pra ativar de verdade (ação do Gabriel, fora do código):**
  1. Virar afiliado Shopee (cadastro pessoal, grátis, sem exigência de
     vendas prévias);
  2. Pedir liberação de API pelo painel de afiliado (formulário de
     suporte) — credenciais (`app_id`/`app_secret`) chegam por e-mail,
     prazo variável, até ~2 semanas segundo relatos;
  3. Preencher `SHOPEE_APP_ID` / `SHOPEE_APP_SECRET` no `.env`.
- **Limitações conhecidas:**
  - o código em `app/sources/shopee.py` usa os nomes de campo
    DOCUMENTADOS publicamente (`itemId`, `productName`, `price`,
    `priceMax`, `sales`, `offerLink`, `shopName`, ...), mas **isso ainda
    não foi validado contra uma resposta real**, porque não há
    credenciais neste ambiente — rodar
    `python -m app.sources.shopee "notebook"` assim que as credenciais
    existirem, e ajustar `normalizar()` se algum nome divergir;
  - rate limit da Shopee não tem número público confirmado — o código
    respeita um intervalo mínimo configurável entre chamadas
    (`SHOPEE_MIN_INTERVAL_SECONDS`) e trata o erro 10030 (limite
    excedido) como falha recuperável, mas isso é uma salvaguarda
    conservadora, não um valor oficial;
  - a API não expõe disponibilidade de estoque nem frete — por isso esses
    campos não entraram em `Product` (ver `docs/data-model.md`).
- **Custo:** zero — o modelo é comissão sobre venda gerada pelo link de
  afiliado (gerado manualmente pelo Gabriel, fora do pipeline automático,
  decisão já registrada antes desta).
- **Manutenção:** uma única fonte, isolada em `app/sources/shopee.py`,
  atrás da interface `OfferSource` — trocar ou adicionar fonte não exige
  tocar em `main.py`/`scoring.py`/`message.py`.
- **Riscos:** dependência de uma única fonte (mitigado pela abstração
  `OfferSource`, que já deixa o projeto pronto pra somar AliExpress como
  segunda fonte sem refatoração); possibilidade de a Shopee também revisar
  política de acesso de terceiros no futuro (mesmo risco que qualquer
  integração de plataforma teria).

### Mercado Livre — quando reavaliar

Fica registrado como decisão arquitetural, não removido: **se** o Gabriel
conseguir certificação de parceiro de desenvolvedor do Mercado Livre (via
contato direto, não self-service), `app/sources/mercadolivre.py` já tem a
normalização pronta e testada — só é preciso trocar
`forcar_tentativa=False` pra `True` (ou reativar sem esse parâmetro) depois
de confirmar contra uma resposta real. Não vale a pena insistir num
caminho de OAuth/certificação "às cegas": é esforço alto, sem prazo, e sem
garantia de resposta, pro estágio atual do projeto (MVP pessoal, não
comercial).

### AliExpress — candidata a segunda fonte

Registrado no roadmap (`docs/roadmap.md`) como o próximo passo natural
depois do MVP: acesso mais rápido de conseguir (~2 dias úteis vs. até ~2
semanas da Shopee) e rate limit maior (5.000 req/dia documentado), útil
pra ampliar catálogo de eletrônicos/gadgets. A ressalva de frete lento
pesa menos numa segunda fonte usada pra comparação de preço do que numa
fonte única de "oferta pra comprar agora".

## D. Como a nova fonte se encaixa na arquitetura

Ver `docs/architecture.md` (atualizado) para o diagrama completo. Resumo:

```
app/sources/base.py        → OfferSource (interface) + OfferSourceError
app/sources/shopee.py      → ShopeeSource(OfferSource)   [ativa, padrão]
app/sources/mercadolivre.py→ MercadoLivreSource(OfferSource) [desativada]
app/config.py              → get_source() escolhe a fonte por env (OFFER_SOURCE)
app/main.py                → só chama get_source().buscar_produtos(query)
```

Nenhuma parte fora de `app/sources/*` sabe o nome de um campo específico
de uma fonte (`itemId`, `permalink`, etc). Isso é o que o projeto pedia
desde `docs/architecture.md` original — só que agora com uma segunda
implementação de verdade pra provar que a interface funciona, não só a
teoria.

## E. Próximos passos pra virar um MVP operacional

1. Gabriel: cadastrar-se como afiliado Shopee e pedir liberação de API
   (único passo que não pode ser automatizado — exige dados pessoais/de
   pagamento do próprio Gabriel).
2. Preencher `.env` com `SHOPEE_APP_ID`/`SHOPEE_APP_SECRET` reais.
3. Rodar `python -m app.sources.shopee "notebook"` e comparar o JSON cru
   contra o que `normalizar()` espera — corrigir nomes de campo se a API
   real divergir da documentação.
4. Rodar a dashboard (`uvicorn app.main:app --reload`) contra dados reais
   e validar o pipeline ponta a ponta com uma consulta de verdade.
5. Persistência simples dos produtos coletados (ainda não existe — ver
   `docs/roadmap.md`), pré-requisito pra sair do "compara só com a mesma
   busca" e chegar em histórico de preço de verdade.
6. Avaliar AliExpress como segunda fonte, seguindo o mesmo padrão
   (`app/sources/aliexpress.py` implementando `OfferSource`).

## F. Atualização (2026-09-15/16): pivô para scraping

As seções A-E acima levaram à escolha da Shopee como fonte via API. Na
prática, o passo 1 da seção E ("Gabriel: cadastrar-se como afiliado
Shopee...") depende de aprovação externa (~2 semanas segundo relatos), o
que deixava o MVP inteiro parado esperando um terceiro.

**Decisão (2026-09-15):** em vez de esperar, Gabriel escolheu construir a
coleta do Mercado Livre via **scraping com Playwright** (simular um
navegador real lendo a página pública de busca), aceitando conscientemente
o risco que isso implica: o HTML de um site muda com mais frequência que
um contrato de API, e scraping de página de busca não tem a mesma garantia
contratual que uma API oficial teria. Esse risco foi considerado aceitável
pro estágio atual (validação pessoal, não produto comercial), com uma
condição mantida desde o início do projeto: nenhuma técnica de evasão
(sem burlar CAPTCHA, sem mascarar automação, sem IP rotation) — se uma
página de bloqueio/verificação for detectada, a coleta para e reporta
erro (ver `app/sources/mercadolivre_scraper.py` e o princípio já registrado
em `docs/roadmap.md`, seção "Não é prioridade agora").

**Implementação (2026-09-16):** `app/sources/mercadolivre_scraper.py`
implementa `OfferSource` completo — download (Playwright) → extração
(BeautifulSoup + dict `SELECTORS`) → normalização (`Product`) — e passou a
ser a fonte padrão (`FONTE_PADRAO` em `app/config.py`), porque funciona
sem nenhuma credencial, ao contrário da Shopee.

**O que isso muda, e o que não muda:**

- `MERCADO LIVRE = ROADMAP` (linha da seção C) não vale mais como estava
  escrito: o Mercado Livre voltou a ser MVP, só que por scraping, não pela
  API bloqueada (essa continua bloqueada e descartada, sem mudança — ver
  seção A).
- A comparação Shopee vs. AliExpress (seção B) continua válida: a Shopee
  continua implementada e pronta pra ativar assim que houver credencial,
  e AliExpress continua sendo a candidata natural a próxima fonte.
- `app/sources/mercadolivre.py` (a versão via API) não foi apagada, só
  renomeada pra `mercadolivre_api` em `app/config.py` — fica como
  referência caso a certificação de parceiro do Mercado Livre um dia se
  torne viável (ver seção "Mercado Livre — quando reavaliar" acima, ainda
  válida).
