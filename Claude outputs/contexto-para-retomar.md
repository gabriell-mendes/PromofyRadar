# Contexto do projeto "grupo-de-ofertas" (retomando sessão anterior)

Estou construindo o `grupo-de-ofertas`, um projeto pessoal de automação de Deal Alerts/afiliados (Python + FastAPI + Playwright), dentro de um projeto Claude chamado "Projeto Automação e Ofertas" que já tem instruções de projeto definindo como você deve me ajudar: agir como arquiteto/mentor/code reviewer, explicar conceitos e arquitetura antes de implementar, dividir em etapas pequenas, me deixar tentar antes de entregar solução pronta, diferenciar MVP de melhorias futuras, evitar overengineering, e nunca propor formas de burlar CAPTCHA/anti-bot/autenticação. Regras de escrita: sem travessão (—), emojis minimizados.

Estou anexando o zip `grupo-de-ofertas.zip` com o estado do projeto ANTES dessa mudança de rumo (mas já com toda a base de scraping, filtro, score e o começo da persistência). Descompacte e use como ponto de partida real, os detalhes abaixo é que dizem o que muda a partir daqui.

## Mudança de rumo decidida agora (ainda não implementada)

O HTTP 403 do Mercado Livre voltou a acontecer mesmo depois de eu corrigir o bug do cache de instância em `get_source()`. Percebi (e concordo) que a causa raiz é de arquitetura, não só do bug: hoje a rota `GET /` da dashboard busca ao vivo no Mercado Livre toda vez que a página é carregada. Cada F5, cada navegação de volta, é uma requisição nova pro Mercado Livre. Isso é exatamente o padrão que dispara bloqueio por rate limit.

Decisão: a dashboard passa a ser **só de monitoramento** (somente leitura do que já foi coletado, zero rede ao carregar a página). Buscar ofertas novas vira uma ação separada, manual, disparada por mim quando eu quiser (CLI), não mais acoplada a abrir a página.

Isso separa duas responsabilidades que hoje estão fundidas:

- **Coleta**: busca -> filtra por desconto -> pontua (Deal Score) -> salva no banco (`storage.salvar_oferta`). Isso é o que dispara requisições pro Mercado Livre, então precisa ser espaçado e controlado por mim, não pela dashboard.
- **Monitoramento**: lê o banco (`storage.listar_ofertas`, `storage.contar_por_status`) e mostra na tela, com ação de marcar como enviada. Isso NUNCA deveria tocar a rede.

### O que isso muda nos arquivos (ainda por implementar no novo chat)

1. **Novo módulo de coleta** (ex: `app/collect.py`), com uma CLI (`python -m app.collect "notebook" --desconto-min 50`), reaproveitando a lógica que hoje está em `montar_review_items()` dentro de `app/main.py`: busca via `get_source()`, filtra via `atende_desconto_minimo`, pontua via `calcular_deal_score`/`gerar_motivo`, e no final chama `storage.salvar_oferta(...)` pra cada item que passou no filtro. Esse é o único lugar do projeto que ainda fala com o Mercado Livre.
2. **`app/main.py` vira só leitura**: a rota `/` deixa de chamar `fonte.buscar_produtos()`. Passa a montar a lista a partir de `storage.listar_ofertas()` (provavelmente filtrando por `status=pendente` por padrão, já que "pendente" = "já passou no filtro, ainda não decidi o que fazer"). O formulário de busca (`q`, `desconto_min`) sai da dashboard porque busca não é mais uma ação de página, é uma ação de CLI.
3. **`/historico` continua existindo** como estava planejado: mostra tudo (pendente + enviada), com contadores. A diferença é que agora `/` e `/historico` são as duas telas de leitura do mesmo banco, só com filtro de status diferente, e nenhuma delas dispara rede.
4. **Rota `/marcar-enviada`**: continua exatamente como planejado (GET, chama `storage.marcar_status(..., STATUS_ENVIADA)`, redireciona de volta).
5. **`app/storage.py`**: sem mudança nenhuma, já estava desenhado certo pra esse uso (é por isso que a persistência que eu já tinha pedido pra construir continua valendo, só muda QUEM chama `salvar_oferta`).
6. **`app/filtro.py` e `app/scoring.py`**: sem mudança, continuam sendo chamados pelo novo `app/collect.py` em vez de por `app/main.py`.
7. **README.md e docs**: vão precisar de atualização explicando o novo fluxo em duas etapas (rodar a coleta manualmente de vez em quando, depois abrir a dashboard só pra olhar/decidir), deixando claro que a dashboard sozinha não faz rede nenhuma.

### Por que isso resolve o 403 (e não é só estética)

Rede só acontece quando eu explicitamente rodo `python -m app.collect ...`, no meu ritmo, com o rate limit (`MERCADOLIVRE_MIN_INTERVAL_SECONDS`) fazendo sentido de novo (ele já existia, mas era mascarado pelo fato de a dashboard também bater na rede). Abrir/atualizar a dashboard nunca mais deveria gerar tráfego pro Mercado Livre, então nunca mais deveria, por si só, causar um 403.

## Estado da arquitetura antes dessa mudança (pra referência)

- `OfferSource` é uma classe base (Template Method): cada fonte implementa `buscar_produtos_raw()` + `normalizar()`; `buscar_produtos()` (dedup/descarte de itens inválidos) é implementado uma vez na base.
- Fonte ativa por padrão: `app/sources/mercadolivre_scraper.py` (`MercadoLivreScraperSource`, `name="mercadolivre"`), scraping real via Playwright + BeautifulSoup, seletores CSS em tuplas de fallback (`SELECTORS`), extração cuidadosa de preço atual vs. anterior, rate limiting via `MERCADOLIVRE_MIN_INTERVAL_SECONDS`.
- `app/sources/mercadolivre.py` (API oficial) renomeada pra `name="mercadolivre_api"`, mantida só como referência histórica (bloqueada por política do Mercado Livre, ver `docs/decisao-fonte-de-dados.md`).
- `app/sources/shopee.py` segue existindo, precisa de credenciais que ainda não configurei.
- `app/config.py`: `FONTES` dict + `get_source()` com cache `_INSTANCIAS` (bug real corrigido: sem cache, uma instância nova era criada a cada chamada e o rate limiter nunca funcionava entre requisições).
- `app/filtro.py`: desconto mínimo absoluto (`calcular_desconto_percentual`, `atende_desconto_minimo`), separado do Deal Score relativo (`app/scoring.py`, baseado na mediana dos preços da própria busca).
- `app/storage.py`: já completo. Tabela `ofertas` chave `(source, source_id)`; funções `inicializar_banco()`, `salvar_oferta(produto, score, reason, desconto_percentual)`, `marcar_status(source, source_id, status)`, `listar_ofertas(status=None, limit=200)`, `obter_status(source, source_id)`, `contar_por_status()`; constantes `STATUS_PENDENTE`/`STATUS_ENVIADA`; `DB_PATH = app/../data/ofertas.db`.
- `app/collector.py` e o `app/scraper.py` antigo já foram removidos do pacote (obsoletos).
- README.md e os 4 docs (`docs/architecture.md`, `docs/roadmap.md`, `docs/decisao-fonte-de-dados.md`, `docs/data-model.md`) já passaram por revisão de coerência, mas descrevem o fluxo ANTIGO (dashboard buscando ao vivo) e vão precisar de atualização pra refletir a separação coleta/monitoramento.
- Testes (`tests/test_message_and_config.py`, `tests/test_mercadolivre_source.py`) já ajustados pra mudança de fontes, mas ainda testam contra o fluxo antigo em partes.
- Telegram/bot: ainda não implementado, não tenho bot nem grupo criados, continua fora de escopo por enquanto.

## Próximo passo concreto no novo chat

Não pular direto pra código. Primeiro validar comigo o desenho de `app/collect.py` (o que ele recebe, o que ele imprime/loga, se ele deveria aceitar múltiplas queries numa run só) antes de escrever a solução de referência, depois deixar eu tentar uma primeira versão, revisar, só então seguir pra reescrever `app/main.py` como camada só de leitura.
