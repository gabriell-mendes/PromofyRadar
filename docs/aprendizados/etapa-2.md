# Etapa 2: painel online mínimo (FastAPI + SQLite)

Resumo de conceitos para levar ao Obsidian.

## O que foi feito

Pasta `painel_online/`:

| Arquivo | Papel |
|---|---|
| `db.py` | Conexão SQLite, as 5 tabelas, transação, hash e criação de token |
| `auth.py` | Dependência `usuario_atual`: lê `Authorization: Bearer`, confere o hash no banco |
| `ingest.py` | Valida cada oferta, decide novo/atualização, grava oferta e linha de preço |
| `app.py` | Rotas, limite de tamanho, tela estática |
| `cli.py` | `python -m painel_online.cli NOME` cria usuário e token (provisório até a Etapa 3) |
| `static/index.html` | Tela de listagem simples, com token colado à mão |

Rotas: `POST /api/ingest`, `GET /api/ofertas?status=ativas|descartadas|todas`, `POST /api/descartar`, `POST /api/restaurar`. Todas exigem token por enquanto.

## Conceitos

**SQLite em vez de JSON.** Vários PCs podem enviar ao mesmo tempo. Com um arquivo JSON, duas gravações simultâneas se atropelam. O SQLite trava a escrita e garante "tudo ou nada".

**Transação.** Um bloco de operações que ou grava tudo ou nada. Usamos `BEGIN IMMEDIATE`: a escrita é reservada no início, então a checagem "esse produto já existe?" e o `INSERT` acontecem sem ninguém no meio. Sem isso, dois envios do mesmo produto poderiam criar duplicado. A restrição `UNIQUE (loja, id_produto)` é a segunda camada de proteção, no próprio banco.

**Upsert na prática.** `decidir()` (Etapa 1) responde "novo" ou "atualizacao". Se novo, `INSERT`. Se atualização, `UPDATE`. Nos dois casos entra uma linha em `precos`, formando o histórico.

**Token de API e hash.** O token é uma senha longa e aleatória (`td_` + 256 bits). No banco guardamos só o `sha256` dele. Se alguém copiar o banco, não consegue usar os tokens. Para senha de gente (Etapa 3) usaremos bcrypt, que é lento de propósito, porque senha humana é fraca. Token aleatório é forte, então sha256 basta.

**`enviado_por` vem do token.** O cliente pode até mandar esse campo no JSON: o pydantic ignora campos desconhecidos. Quem define é o servidor, a partir do token. Um teste cobre isso.

**Validar item por item.** O corpo é `{"ofertas": [...]}` e cada item passa por `OfertaIn` separadamente. Uma oferta ruim vira "ignorada" com motivo, e as boas entram. A resposta traz `criadas`, `atualizadas`, `ignoradas`.

**Limites.** No máximo 500 ofertas por envio (422) e 1 MB de corpo (413). Isso protege o servidor de um envio gigante ou de um bug no cliente.

**XSS.** Título e link vêm de dados enviados por outros PCs. A tela monta tudo com `textContent` (nunca `innerHTML`), e `OfertaIn` recusa `url` e `imagem` que não comecem com `http://` ou `https://`, barrando `javascript:`.

**Descartados compartilhados.** Descartar não apaga a oferta: cria uma linha em `descartados`. Todos os admins veem o mesmo estado. Reenviar um produto descartado é ignorado, para ele não reaparecer.

## Achado com dado real

Validar com o `ofertas.json` verdadeiro revelou um bug antigo em `historico.chave_produto`: 5 produtos de links `/up/MLBU...?pdp_filters=deal:MLB779362-1` viravam a mesma chave, porque o regex pegava o id da promoção na query string. Corrigido (o código agora é procurado só no caminho e aceita `MLBU`), com teste de regressão. Isso também melhora o histórico local do Deal Score. Lição: validar com dado real antes de avançar encontra o que o teste sintético não acha.

## MVP, melhoria futura, desnecessário

- MVP: o que foi feito.
- Melhoria futura: paginação real em `GET /api/ofertas`, endpoint de histórico de preços por oferta, limite de tamanho também para corpo sem `Content-Length` (o Caddy reforça na Etapa 5), recalcular Deal Score de forma central.
- Desnecessário agora: ORM, migrações automáticas, fila de envio.
- Provisório: acesso por token colado na tela e `cli.py`. Ambos mudam na Etapa 3.
