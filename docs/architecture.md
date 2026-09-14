# Arquitetura

## Estado atual

MVP em andamento. Existe uma fonte real funcionando de ponta a ponta
(Shopee Affiliate Open API), atrás de uma interface comum a qualquer
fonte (`OfferSource`), e uma dashboard de revisão manual ligada nela. Ver
`docs/decisao-fonte-de-dados.md` pra como e por que a Shopee foi escolhida
(e por que Mercado Livre não é uma fonte viável agora).

## Fluxo de dados (MVP)

```
consulta (string)
    │
    ▼
OfferSource.buscar_produtos()  → busca produtos numa fonte concreta
    │                             (app/sources/shopee.py, hoje) e já
    │                             devolve Product normalizado, descartando
    │                             itens sem preço/link válido ou duplicados
    ▼
análise / Deal Score → calcula uma nota da oferta a partir de regras
                       explícitas sobre os dados coletados (não é IA)
    │
    ▼
filtro                → decide quais ofertas passam do score mínimo
    │
    ▼
geração de mensagem  → monta o texto pronto para publicação
    │
    ▼
revisão manual        → você decide se publica (no MVP, é sempre manual)
```

Diferença em relação à primeira versão deste documento: busca e
normalização, que antes eram duas etapas separadas descritas aqui,
viraram uma responsabilidade só de cada fonte (`OfferSource.buscar_produtos`,
implementado uma vez em `app/sources/base.py`, herdado por toda fonte
concreta) — porque normalizar sem tolerar item ruim/duplicado não
funciona de verdade contra uma API real (ver `docs/decisao-fonte-de-dados.md`,
seção de testes).

## Por que separar fonte / análise?

Cada fonte de dados (Shopee, Mercado Livre, AliExpress no futuro) devolve
os dados em um formato diferente, com autenticação e regras de rate limit
próprias. Se misturarmos "buscar dados" com "decidir se é uma boa oferta",
qualquer mudança de fonte quebra a lógica de negócio junto — foi
exatamente esse acoplamento que teria tornado a substituição do Mercado
Livre pela Shopee um retrabalho grande, se não existisse a interface.

Separando em camadas:
- **`app/sources/<fonte>.py`** conhece só a fonte (API/protocolo dela) —
  autentica, pagina, respeita rate limit, transforma item cru em `Product`.
  Não sabe o que é um "bom desconto".
- **`app/sources/base.py` (`OfferSource`)** define o contrato comum
  (`buscar_produtos_raw`, `normalizar`) e implementa, uma vez só, o que é
  igual pra qualquer fonte: descartar item inválido/duplicado sem derrubar
  a busca inteira.
- **`app/config.py` (`get_source`)** é o único lugar que sabe "qual fonte
  concreta existe pra cada nome" — troca de fonte é mudar uma variável de
  ambiente (`OFFER_SOURCE`), não código em `main.py`.
- **análise/Deal Score (`app/scoring.py`)** conhece só regras de negócio
  sobre um `Product` já normalizado — não sabe de onde ele veio.

Isso deixa cada peça pequena, testável isoladamente (ver `tests/`), e
permitiu adicionar a Shopee como segunda fonte de verdade sem tocar em
`main.py`, `scoring.py` ou `message.py` — só criando
`app/sources/shopee.py` e registrando em `app/config.py`.

## Decisões técnicas

| Decisão | Motivo |
|---|---|
| Fonte do MVP: Shopee Affiliate Open API, não Mercado Livre | Mercado Livre bloqueia terceiros não certificados (`PA_UNAUTHORIZED_RESULT_FROM_POLICIES`) — ver `docs/decisao-fonte-de-dados.md` |
| Fonte acessada via API oficial, não scraping de HTML | Mais estável, sem risco de bloqueio, sem questões de ToS |
| Toda fonte concreta implementa `OfferSource` | Permite trocar/somar fonte sem espalhar `if fonte == "x"` pelo projeto |
| Sem banco de dados "de verdade" ainda | Adiar Postgres até termos coleta real validada — evita configurar infraestrutura antes de validar a coleta |
| Deal Score começa simples (mediana da busca + penalidade leve por zero vendas) | Um score de 0-100 complexo sem histórico de preços real seria arbitrário |
| Sem uso de LLM na decisão de "boa oferta" | Decisão quantitativa deve vir de regras sobre dados, não de opinião de IA |
| Geração de link de afiliado é manual, fora do pipeline | Relaxa o requisito de uma fonte específica ter API de afiliado — só precisa de API de produto/preço oficial |

## Como isso pode evoluir

- Armazenamento simples → PostgreSQL com schema de produto/oferta/preço/loja
- 1 fonte (Shopee) → múltiplas fontes atrás da mesma interface `OfferSource`
  (AliExpress é a próxima candidata natural — ver `docs/decisao-fonte-de-dados.md`;
  Mercado Livre volta a ser avaliado se/quando certificação de parceiro
  existir)
- Deal Score simples → fatores adicionais conforme histórico de preços existir
- Geração de mensagem manual → bot do Telegram publicando automaticamente
- Revisão manual → aprovação automática acima de um score de confiança alto
