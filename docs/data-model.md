# Modelo de dados

Implementado em `app/models.py` — se um campo mudar lá, atualize este
documento (e vice-versa).

## Product

O objeto normalizado que sai de qualquer fonte (`app/sources/*.py`),
independente de qual seja.

| Campo | Tipo | Descrição | Quem preenche hoje |
|---|---|---|---|
| `source` | str | de qual fonte veio (ex: "shopee", "mercadolivre") | todas |
| `source_id` | str | id do produto/anúncio na fonte | todas |
| `title` | str | título do produto | todas |
| `price` | Decimal | preço atual | todas |
| `url` | str | link direto para o produto (não é link de afiliado — ver `docs/decisao-fonte-de-dados.md`) | todas |
| `store` | str | nome da loja/vendedor | todas |
| `collected_at` | datetime | quando foi coletado | todas |
| `original_price` | Decimal \| None | preço "de" anunciado pela fonte/loja, quando existe | Shopee, Mercado Livre |
| `image_url` | str \| None | imagem do produto, quando a fonte fornece | Shopee, Mercado Livre |
| `sales` | int \| None | volume de vendas reportado pela fonte, usado como sinal leve de confiança no Deal Score | só Shopee |

`original_price`, `image_url` e `sales` são opcionais (`None` quando a
fonte não fornece) de propósito: nenhum campo foi adicionado só por
completude — cada um já é lido em algum lugar do pipeline (mensagem de
publicação, dashboard, ou `app/scoring.py`).

## Fora do MVP (registrado aqui para não esquecer, não para implementar já)

- `Offer` — separaria "produto" de "oferta pontual" quando tivermos mais
  de uma fonte por produto
- `PriceHistory` — série temporal de preços por produto (pré-requisito
  real pra sair de "compara só com a mesma busca" — ver `docs/decisao-fonte-de-dados.md`,
  seção "Próximos passos")
- `Store` — confiabilidade, frete, cupons
- `DealScore` — score calculado, com breakdown dos fatores que geraram a nota
- `availability` (disponibilidade/estoque) e `category` — cogitados
  durante a investigação de fontes, mas nenhuma fonte atual (Shopee,
  Mercado Livre) fornece esse dado de forma confiável pela API de busca —
  não adicionados até existir uma fonte real que os preencha
