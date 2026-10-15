# Etapa 7: teste de ponta a ponta

Resumo de conceitos para levar ao Obsidian.

## O que foi feito

| Item | Para que serve |
|---|---|
| `tests/test_painel_online_etapa7.py` | 5 testes: um cenário com dois PCs, do envio à consulta no painel |
| Teste do envio com processos reais | Painel local e painel online temporário rodando de verdade, envio pela API |
| Teste do botão no navegador | Chromium headless clicando em "Enviar ao painel" e na barra de seleção |
| `docs/compartilhamento-de-dados.md` | Status da Etapa 7, regra do `enviado_por` e pergunta frequente sobre os testes |
| `docs/deploy-vps.md` | Seção 0 corrigida (o código já está no `main`) e seção 12 com a rodada real em duas partes |

**O que NÃO foi feito:** a rodada real contra o VPS. Ela depende do deploy da Etapa 5, que depende do seu servidor e do seu SSH. A seção 12 do roteiro está pronta para você rodar.

## O que o teste prova

Dois PCs (clientes sem cookie, cada um só com o seu token) e dois administradores (clientes com cookie):

1. A Ana envia o produto `MLB25171538` a 100,00. A Bia envia o **mesmo produto**, com outro link, a 90,00. Resultado: continua **uma** linha em `ofertas`, e `precos` guarda os dois valores, cada um com o autor certo.
2. O painel mostra o preço do último envio (90,00), `n_precos = 2` e `enviado_por = bia`.
3. A Bia tenta forjar `enviado_por: "ana"` no corpo. O servidor ignora o campo e grava o dono do token.
4. Reenviar o mesmo lote três vezes não duplica a oferta, só soma linhas no histórico.
5. Descarte feito por uma pessoa vale para o PC da outra: o reenvio vira "ignorada" com o motivo.
6. Sem login, `/` e `/tokens` redirecionam para `/login` e `/api/ofertas` dá 401.
7. Token de API não abre o painel, e o cookie não serve para enviar ofertas.

## Conceitos

**Teste de cenário.** Os testes das etapas anteriores olham uma peça por vez (contrato, upsert, login). Este conta uma história inteira, na ordem em que ela acontece de verdade. Ele pega o que os testes pequenos não pegam: peças que funcionam sozinhas mas combinam mal.

**Clientes separados simulam máquinas separadas.** Cada `TestClient` tem o seu próprio conjunto de cookies. Um sem cookie e com token é um "PC"; um com cookie é um administrador no navegador. Assim o teste exercita as duas credenciais ao mesmo tempo.

**Teste via API não é teste de interface.** A API pode estar certa e o botão errado (texto, confirmação, etiqueta, botão que não reativa). Por isso o botão foi testado também num navegador de verdade. O limite: a rede de teste não alcançava o CDN do Tailwind, então o visual não foi avaliado, só o comportamento.

**Decisão: ignorar campo desconhecido, ou recusar?** O plano original dizia "`enviado_por` forjado é recusado". Hoje o pydantic descarta campos que não conhece, e o servidor grava o dono do token. Recusar com 422 (`extra='forbid'`) deixaria o contrato mais rígido, mas traria um risco real: um PC com código mais novo que o servidor, mandando um campo novo, teria o lote inteiro recusado. A decisão adotada foi **ignorar**, que já é segura (o valor forjado nunca chega ao banco) e está coberta por teste. Se um dia quiser saber quem tenta forjar, dá para registrar no log sem recusar. Foi uma recomendação minha: se você preferir o 422, é uma linha no `OfertaIn` mais um teste.

**Idempotência de novo.** Reenviar é seguro porque a chave `(loja, id_produto)` não muda, mesmo com links diferentes do mesmo produto. A correção da Etapa 2 (id da promoção na query string) é o que faz o cenário da Ana e da Bia funcionar.

## Validado aqui

- Suíte completa: 165 passed (em Linux; no Windows o teste de permissão de arquivo fica de fora).
- Envio com dois servidores reais: 3 criadas, 1 ignorada por imagem `javascript:`, oferta de teste nunca enviada, reenvio atualiza e soma uma linha no histórico, POST sem `X-TechDrop` dá 403, token errado dá 401 com mensagem em português, painel fora do ar dá 502 com mensagem clara.
- Botão no navegador: o contador `(N)`, a janela de confirmação com o destino, o botão Cancelar (não envia nada), a etiqueta NO PAINEL, o contador caindo depois do envio e o aviso "já foram enviadas antes: serão atualizadas" no reenvio pela barra de seleção.

## Achados

- **Resolvido depois:** a oferta recusada pelo painel agora ganha `recusada_painel_em` e `recusada_painel_motivo` em `ofertas.json`, a etiqueta RECUSADA (com o motivo ao passar o mouse) e sai do contador "Enviar ao painel (N)". O envio de todas as pendentes não a reenvia; escolhendo-a à mão ela vai de novo, e se der certo a marca some. Nova coleta do produto zera a marca.
- O visual do painel local depende do CDN do Tailwind. Sem internet, a página abre sem estilo.

## Não validado

A rodada contra o VPS real, com HTTPS e dois usuários de verdade (`docs/deploy-vps.md`, seção 12). A coleta real no Mercado Livre num PC novo e o download do Chromium também seguem sem validação.

## MVP, melhoria futura, desnecessário

- MVP: o que foi feito.
- Melhoria futura: teste de navegador automatizado e opcional dentro do projeto (exige Playwright nos testes), registrar no log quem tentou forjar `enviado_por`.
- Desnecessário agora: `extra='forbid'` no contrato, ferramentas de teste de carga.
