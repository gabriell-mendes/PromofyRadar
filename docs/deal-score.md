# Deal Score

Nota de 0 a 100 calculada por regras explícitas (`deal_score.py`), sem IA decidindo.
Escala: 0 = não está mais barato que o normal. 100 = pelo menos 30% abaixo da referência.

## Fluxo

```
scraper lê a página
  -> todos_vistos (todo item lido, mesmo o cortado pelo desconto mínimo)
  -> resultados (itens que passaram no filtro)
  -> pontuacao.pontuar_e_ordenar
       1. busca no histórico os preços dos dias ANTERIORES de cada produto
       2. deal_score.avaliar (nota, confiança, motivos, flags)
       3. grava os preços de hoje no histórico
  -> JSON com deal_score, deal_confianca, deal_motivos, deal_flags
  -> painel (badge, filtro "Deal Score mín", ordenação)
```

## Fatores

| Fator | Peso | Regra |
|---|---|---|
| historico | 50 | desconto real contra a mediana dos últimos 30 dias do próprio produto |
| grupo | 30 | desconto real contra a mediana dos preços da mesma coleta |
| minimo | 20 | proximidade do menor preço recente, na proporção do desconto real |

Desconto real = (referência - preço) / referência, com teto em 30%.
Fatores sem dados saem da conta e os pesos restantes são renormalizados.

- Sem histórico (menos de 3 dias): só o grupo vale, confiança "baixa".
- Sem histórico e com menos de 5 itens no grupo: sem nota (None).
- Preço inválido: sem nota, flag `preco_invalido`.
- O desconto anunciado pela loja nunca soma pontos. Só gera a flag `desconto_inflado`
  (quando o "de" está mais de 20% acima do preço normal provado pelo histórico).
- Flag `menor_preco_recente`: preço abaixo de tudo que o histórico registrou.

## Limitações conhecidas

- Coletas por categoria ou aba de Ofertas misturam produtos diferentes. A mediana do grupo
  ali é fraca. O histórico do próprio produto resolve isso com o tempo (confiança "alta").
- Uma nota de confiança "baixa" pode superar uma de confiança "alta" na ordenação. O painel
  mostra a confiança em cada card, ajuste os pesos em `deal_score.py` se isso incomodar.
- Frete, cupom, disponibilidade e confiabilidade da loja ainda não entram (não há dado).

## Arquivos

- `deal_score.py`: regras (função pura)
- `historico.py`: SQLite `data/historico_precos.db`, um preço por produto por dia
- `pontuacao.py`: liga as duas coisas para uma coleta
- `teste_base.py` e `scraper_teste_*.py`: scrapers simulados com cenários conhecidos
- `frontend/iniciar_teste.bat`: abre o painel usando os scrapers de teste
- `tests/test_deal_score.py`, `tests/test_historico.py`, `tests/test_scrapers_teste.py`
