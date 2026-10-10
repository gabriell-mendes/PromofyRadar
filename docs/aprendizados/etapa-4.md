# Etapa 4: botão "Enviar ao painel"

Resumo de conceitos para levar ao Obsidian.

## O que foi feito

- `techdrop_server.py`: `GET /api/painel/status` e `POST /api/painel/enviar`, mais funções de apoio (`_config_painel`, `_validar_url_painel`, `_para_painel`, `_erro_painel`, `_marcar_enviadas`).
- `frontend/index.html` e `frontend/assets/app.js`: botão "Enviar ao painel (N)" no topo, botão na barra de seleção, confirmação antes de enviar, etiqueta "NO PAINEL" nos cards.
- `.env.example`: `PAINEL_URL` e `PAINEL_TOKEN` comentados, no fim do arquivo (o resto ficou intocado).
- `tests/test_painel_local_etapa4.py`: 16 testes, com o painel online subindo de verdade numa thread (HTTP real, não mock).

## Conceitos

**O painel local virou cliente.** O navegador local só pede "enviar estas ofertas". Quem fala com o painel online é o `techdrop_server.py`, que lê o token do `.env`. Assim o token nunca passa pelo JavaScript da página, onde um XSS poderia roubá-lo.

**Adaptador de formato.** O scraper fala `title`, `price`, `link`; o painel online fala `titulo`, `preco`, `url` (o contrato `OfertaIn` da Etapa 1). `_para_painel` faz a tradução em um lugar só. `coletado_em` é preenchido aqui, no momento do envio.

**Ler `.env` sem poluir o ambiente.** O servidor local dispara o scraper como subprocesso herdando `os.environ`. Se carregássemos o `.env` com `load_dotenv`, o `PAINEL_TOKEN` iria junto para o scraper, que não precisa dele. Por isso usamos `dotenv_values`, que apenas lê o arquivo. Teste garante que o token não vai para `os.environ`.

**HTTPS obrigatório para host remoto.** O token vai em todo envio. Por `http` ele trafegaria legível. A validação recusa `http` exceto em `localhost`. E `allow_redirects=False` impede que um redirecionamento leve o header com o token para outro endereço.

**Envio em lotes.** Pedidos de até 200 ofertas, abaixo do limite do painel (500 ofertas, 1 MB). Se a conexão cair no meio, o servidor avisa quantas já chegaram e marca só essas. Como o painel online faz upsert, reenviar o resto é seguro.

**Idempotência.** Repetir a mesma operação não causa estrago: não duplica a oferta. O efeito colateral aceito é uma linha extra no histórico de preços a cada envio (decisão da Etapa 2). Por isso "enviar todas" manda só as pendentes, e reenviar exige selecionar de propósito.

**Marca local de envio.** Cada oferta enviada ganha `enviado_painel_em` no `ofertas.json`. Quando uma nova coleta sobrescreve a oferta (o scraper grava a coleta mais recente por link), a marca some sozinha: é um preço novo, vale enviar de novo.

**Erros em português, com ação.** Cada falha (sem configuração, URL sem https, sem internet, certificado, timeout, token inválido, painel com erro) vira uma mensagem que diz o que fazer. O `api()` do frontend passou a exibir o `detail` que o servidor devolve em vez de "Erro 502".

**Dado de teste não pode vazar.** As ofertas do `iniciar_teste.bat` (campo `teste: true`, links `teste.techdrop.local`) são filtradas no servidor. Defesa no backend, não só no botão, porque o frontend pode ser contornado.

## Achado na validação

Rodando o fluxo real (painel online e local, navegador): seleção de 2 ofertas, confirmação mostrando o destino, envio, etiquetas e contador caindo de 42 para 40, depois o restante em lote (42 ofertas e 42 linhas de preço online). Com o token revogado, a mensagem de erro apareceu clara. O `ofertas.json` real foi restaurado do backup depois, porque o envio grava a marca nele.

## MVP, melhoria futura, desnecessário

- MVP: o que foi feito.
- Melhoria futura: envio automático após a coleta, enviar também as ofertas abertas por "Carregar JSON", fila de reenvio offline, mostrar no painel local o status de cada oferta no painel online.
- Desnecessário agora: fila de mensagens, WebSocket, sincronização do painel online de volta para o local.
