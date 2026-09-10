# Modelo de dados

Ainda não implementado — este documento existe para registrar o desenho
conceitual do MVP. Vai ficar mais detalhado (e provavelmente vai mudar)
conforme o código avança.

## Product (MVP)

O objeto normalizado que sai da etapa de normalização, independente da fonte.

| Campo | Tipo | Descrição |
|---|---|---|
| `source` | str | de qual fonte veio (ex: "mercadolivre") |
| `source_id` | str | id do produto/anúncio na fonte |
| `title` | str | título do produto |
| `price` | Decimal | preço atual |
| `url` | str | link direto para o produto |
| `store` | str | nome da loja/vendedor |
| `collected_at` | datetime | quando foi coletado |

## Fora do MVP (registrado aqui para não esquecer, não para implementar já)

- `Offer` — separaria "produto" de "oferta pontual" quando tivermos mais de
  uma fonte por produto
- `PriceHistory` — série temporal de preços por produto
- `Store` — confiabilidade, frete, cupons
- `DealScore` — score calculado, com breakdown dos fatores que geraram a nota
