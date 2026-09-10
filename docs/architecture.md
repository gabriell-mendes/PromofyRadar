# Arquitetura

## Estado atual

Projeto em setup. Ainda não há código de coleta — este documento descreve a
arquitetura **alvo** para o MVP, que vai sendo implementada aos poucos.

## Fluxo de dados (MVP)

```
consulta (string)
    │
    ▼
collector          → busca produtos numa fonte (ex: API do Mercado Livre)
    │                 e devolve dados "crus" (formato da fonte)
    ▼
normalização        → converte o dado cru da fonte em um objeto Product
                       único e padronizado, independente da fonte
    │
    ▼
armazenamento        → salva o Product coletado (persistência)
    │
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

## Por que separar collector / normalização / análise?

Cada fonte de dados (Mercado Livre, Amazon, etc.) devolve os dados em um
formato diferente. Se misturarmos "buscar dados" com "decidir se é uma boa
oferta", qualquer mudança na fonte quebra a lógica de negócio junto.

Separando em camadas:
- **collector** conhece só a fonte (API/HTML) — não sabe o que é um "bom
  desconto".
- **normalização** conhece só a conversão fonte → `Product` — não faz
  requisições HTTP nem calcula score.
- **análise/Deal Score** conhece só regras de negócio sobre um `Product` já
  normalizado — não sabe de onde ele veio.

Isso deixa cada peça pequena, testável isoladamente, e permite adicionar uma
segunda fonte no futuro sem tocar na lógica de score.

## Decisões técnicas

| Decisão | Motivo |
|---|---|
| Fonte inicial: API oficial, não scraping de HTML | Mais estável, sem risco de bloqueio, sem questões de ToS |
| Sem banco de dados "de verdade" ainda no primeiro passo | Adiar Postgres até termos algo coletando de fato — evita configurar infraestrutura antes de validar a coleta |
| Deal Score começa simples (poucos fatores) | Um score de 0-100 complexo sem dados históricos reais seria arbitrário |
| Sem uso de LLM na decisão de "boa oferta" | Decisão quantitativa deve vir de regras sobre dados, não de opinião de IA |

## Como isso pode evoluir

- Armazenamento simples → PostgreSQL com schema de produto/oferta/preço/loja
- 1 collector → múltiplos collectors atrás de uma interface comum
- Deal Score simples → fatores adicionais conforme histórico de preços existir
- Geração de mensagem manual → bot do Telegram publicando automaticamente
- Revisão manual → aprovação automática acima de um score de confiança alto
