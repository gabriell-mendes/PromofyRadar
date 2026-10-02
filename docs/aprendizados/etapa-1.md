# Etapa 1: contrato da oferta e decisão de upsert

Resumo de conceitos para levar ao Obsidian.

## O que foi feito

- `painel_online/schemas.py`: classe `OfertaIn`, o molde de uma oferta enviada ao painel online.
- `painel_online/upsert.py`: `decidir(oferta, chaves_existentes)` devolve `"novo"` ou `"atualizacao"`.
- `tests/test_painel_online_etapa1.py`: 7 testes.

## Conceitos

**Contrato de dados.** Antes de construir o servidor, combinamos exatamente quais campos uma oferta tem, quais são obrigatórios e quais são opcionais. Quem envia (o PC) e quem recebe (o VPS) concordam com esse molde. Se um dia o formato mudar, muda em um lugar só.

**Pydantic.** Biblioteca que transforma uma classe em um validador. Escrever `preco: float = Field(gt=0)` já garante que o preço é número e maior que zero, sem `if` manual. Dado inválido levanta `ValidationError` antes de chegar perto do banco.

**Obrigatório vs opcional.** Sem valor padrão = obrigatório. `= None` = opcional. `float | None` quer dizer "número ou nada".

**`default_factory=list`.** Para listas, o padrão é uma função que cria uma lista nova a cada oferta, em vez de uma lista única compartilhada.

**Chave de identidade.** Um produto é identificado por `(loja, id_produto)`. O link do Mercado Livre muda a cada busca (`pdp_filters`, `searchVariation`), então o `id_produto` é o código `MLB...` extraído da URL por `chave_produto()`. Dois links diferentes do mesmo produto caem na mesma chave.

**Upsert.** Palavra que junta "update" e "insert": se o produto já existe, atualiza; se não, cria. A função `decidir` só responde a pergunta "já existe?", sem tocar em banco. Isso a torna fácil de testar e deixa o SQLite para a Etapa 2.

**Quem recebe deriva, quem envia não manda.** `id_produto` e `enviado_por` ficam fora do contrato de propósito. Se o cliente pudesse mandar `enviado_por`, um PC poderia se passar por outro usuário. O servidor descobre isso sozinho (pela URL e pelo token).

## MVP, melhoria futura, desnecessário

- MVP: o que foi feito.
- Melhoria futura: validar `desconto` contra os preços, recalcular Deal Score de forma central.
- Desnecessário agora: qualquer lógica de banco no schema.
