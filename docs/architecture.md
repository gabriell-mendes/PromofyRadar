# Arquitetura

## Estado atual

MVP em andamento. A fonte real que roda de ponta a ponta hoje é o
**Mercado Livre via scraping** (`app/sources/mercadolivre_scraper.py`,
Playwright + BeautifulSoup), atrás da interface comum a qualquer fonte
(`OfferSource`), com uma dashboard de revisão manual ligada nela. A
**Shopee Affiliate Open API** (`app/sources/shopee.py`) está implementada
do mesmo jeito, mas ainda sem credenciais reais configuradas.

Ver [`docs/decisao-fonte-de-dados.md`](decisao-fonte-de-dados.md) para o
histórico completo: por que a API oficial do Mercado Livre foi descartada,
por que a Shopee foi escolhida como fonte via API, e por que depois disso
o projeto pivotou pra scraping em vez de esperar aprovação de API.

## Fluxo de dados (MVP)

```
consulta (string)
    │
    ▼
OfferSource.buscar_produtos()  → busca produtos numa fonte concreta
    │                             (app/sources/mercadolivre_scraper.py,
    │                             hoje) e já devolve Product normalizado,
    │                             descartando itens sem preço/link válido
    │                             ou duplicados
    ▼
Deal Score (app/scoring.py)   → nota RELATIVA: quanto mais barato que a
    │                            mediana dos preços encontrados NESTA
    │                            busca, maior a nota. Regra explícita
    │                            sobre os dados coletados, não é IA.
    ▼
filtro de desconto (app/filtro.py) → corte ABSOLUTO: o produto está com
    │                                 desconto real (price vs.
    │                                 original_price) de pelo menos X%?
    │                                 Independente do Deal Score.
    ▼
geração de mensagem (app/message.py) → monta o texto pronto para
    │                                    publicação
    ▼
revisão manual (app/main.py) → você decide se publica; o link de afiliado
                                é gerado por você, fora do código (ver
                                decisão registrada abaixo)
```

Dentro de `OfferSource.buscar_produtos_raw()`, quando a fonte é scraping
(não API), existe uma sub-separação em 3 passos que vale entender porque
se repete em qualquer scraper novo que o projeto ganhar:

```
download   → abre a página com Playwright, devolve o HTML puro
extract    → aplica seletores CSS (dict SELECTORS) sobre esse HTML,
             devolve campos crus (texto, ainda não convertido)
output     → normalizar() converte pra Product (Decimal, validação,
             descarte de item inválido)
```

Isso é o mesmo padrão que uma API já resolve "de graça" (a API devolve
JSON estruturado, não precisa de um passo de extração separado) — só que
scraping precisa das 3 etapas porque o dado começa como HTML, não como
dado estruturado.

## Por que separar fonte / análise / filtro?

Cada fonte de dados (Mercado Livre, Shopee, AliExpress no futuro) devolve
os dados de um jeito diferente — API ou HTML, autenticação e rate limit
próprios. Se misturarmos "buscar dados" com "decidir se é uma boa oferta",
qualquer mudança de fonte quebra a lógica de negócio junto.

Separando em camadas:
- **`app/sources/<fonte>.py`** conhece só a fonte (formato/protocolo dela)
  — autentica ou simula navegador, pagina, respeita rate limit, transforma
  item cru em `Product`. Não sabe o que é um "bom desconto".
- **`app/sources/base.py` (`OfferSource`)** define o contrato comum
  (`buscar_produtos_raw`, `normalizar`) e implementa, uma vez só, o que é
  igual pra qualquer fonte: descartar item inválido/duplicado sem derrubar
  a busca inteira.
- **`app/config.py` (`get_source`)** é o único lugar que sabe "qual fonte
  concreta existe pra cada nome" — troca de fonte é mudar a variável de
  ambiente `OFFER_SOURCE` (ou, por busca, o valor no `?fonte=`, quando
  existir), não código em `main.py`.
- **`app/scoring.py` (Deal Score)** e **`app/filtro.py` (desconto mínimo)**
  conhecem só `Product` já normalizado — não sabem de onde ele veio, nem
  se veio de API ou de scraping. São duas perguntas diferentes sobre o
  mesmo produto (relativa à busca vs. absoluta sobre o próprio preço "de"),
  por isso ficam em arquivos separados, cada um podendo aprovar sem o
  outro.

Isso deixa cada peça pequena, testável isoladamente (ver `tests/`), e já
permitiu trocar a fonte principal de "API do Mercado Livre" pra "Shopee
API" pra "Mercado Livre via scraping" sem tocar em `main.py`, `scoring.py`
ou `message.py` — só criando/trocando o arquivo em `app/sources/` e
registrando em `app/config.py`.

## Decisões técnicas

| Decisão | Motivo |
|---|---|
| Fonte ativa hoje: Mercado Livre via scraping (Playwright) | API oficial bloqueia terceiros não certificados (`PA_UNAUTHORIZED_RESULT_FROM_POLICIES`); scraping foi um pivô consciente depois disso, aceitando o risco de mudança de HTML e de termos de uso — ver `docs/decisao-fonte-de-dados.md` |
| Shopee mantida como segunda fonte via API oficial | Já implementada, só falta credencial (ação pessoal do dono); continua o candidato "mais seguro" (API oficial, sem risco de bloqueio de layout) |
| Toda fonte concreta implementa `OfferSource` | Permite trocar/somar fonte sem espalhar `if fonte == "x"` pelo projeto |
| Scraping sem nenhuma técnica de evasão | Sem mascarar automação, sem burlar CAPTCHA/anti-bot, sem IP rotation; se detectar página de bloqueio/verificação, para e reporta erro em vez de insistir |
| Seletores CSS centralizados num dict (`SELECTORS`) por fonte | Se o site mudar o HTML, o ajuste fica isolado num só lugar por arquivo, sem caçar seletor espalhado pelo código |
| Deal Score (relativo) separado do filtro de desconto (absoluto) | São perguntas diferentes: "tá barato perto dos outros resultados desta busca?" vs. "esse produto específico tem desconto real sobre o próprio preço de?" |
| Sem banco de dados "de verdade" ainda | Adiar Postgres até termos coleta real validada — evita configurar infraestrutura antes de validar a coleta |
| Sem uso de LLM na decisão de "boa oferta" | Decisão quantitativa deve vir de regras sobre dados, não de opinião de IA |
| Geração de link de afiliado é manual, fora do pipeline | Relaxa o requisito de uma fonte específica ter API de afiliado — só precisa de fonte de produto/preço, API ou scraping |

## Como isso pode evoluir

- Armazenamento simples → PostgreSQL com schema de produto/oferta/preço/loja
- Deal Score baseado só na busca atual → fatores adicionais conforme
  histórico de preços existir
- Shopee ativada assim que o dono tiver credenciais; AliExpress como
  candidata natural a terceira fonte (ver `docs/decisao-fonte-de-dados.md`)
- Mercado Livre via API oficial volta a ser avaliado se/quando
  certificação de parceiro existir (`app/sources/mercadolivre.py`, hoje
  registrado como `mercadolivre_api`, já tem a normalização pronta)
- Geração de mensagem manual → bot do Telegram publicando automaticamente
- Revisão manual → aprovação automática acima de um score de confiança alto
