# Prompt para o Claude Code: configurar URL e token do envio direto pelo painel

Cole tudo abaixo no Claude Code, com a pasta `grupo-de-ofertas` aberta na raiz. Leia primeiro o `CLAUDE.md` do projeto: ele manda e este prompt só detalha esta tarefa.

---

## 1. Contexto

Sou o Gabriel. No painel local (`techdrop_server.py` + `frontend/`), o botão "Enviar ao painel" falha com a mensagem:

> Envio não configurado. Preencha PAINEL_URL e PAINEL_TOKEN no .env e reinicie o painel.

Hoje a única forma de configurar é editar o `.env` na mão e reiniciar. Quero **preencher a URL e o token dentro do próprio painel local**, sem editar arquivo e sem reiniciar.

Estado atual do código (já verificado, confirme lendo antes de mexer):

- `techdrop_server.py`: `_config_painel()` lê `PAINEL_URL` e `PAINEL_TOKEN` com `os.environ` primeiro e `dotenv_values(ENV_FILE)` depois, **a cada chamada**. Por isso gravar no `.env` já basta, sem reiniciar. Ele usa `dotenv_values` de propósito: o token **não pode** ir para `os.environ`, senão herda para o subprocesso do scraper.
- `_validar_url_painel(url)` já existe (https obrigatório fora de localhost). Reaproveite.
- `GET /api/painel/status` devolve `{"configurado": bool, "url": str|None}` e nunca o token. Existem testes que comparam esse JSON de forma exata, então **não mude o formato dele**.
- `POST /api/painel/enviar` e as rotas de escrita usam `dependencies=[Depends(somente_painel)]` (header `X-TechDrop: 1`).
- `frontend/assets/app.js`: `enviarAoPainel()` mostra um `toast` com a mensagem acima quando `painel.configurado` é falso. Existem `api(url, body)`, `toast(msg, ms)`, `confirmar(...)`, `carregarPainelStatus()` e um handler de Escape (perto da linha 406) que fecha modais.
- `frontend/index.html`: botão `btnPainel` no topo e modais existentes (`confirmModal`, `modal`), com Tailwind e as cores `bg-panel`, `border-line`, `bg-bg`.
- `tests/test_painel_local_etapa4.py`: fixture `local` (TestClient com `ENV_FILE` apontando para `tmp_path/.env` e `PAINEL_URL`/`PAINEL_TOKEN` removidos do ambiente) e fixture `online` (servidor online real de teste).
- O `.env` real **ainda não existe** na pasta do Gabriel. A gravação precisa criar o arquivo.

## 2. Regras de trabalho (obrigatórias)

1. Antes de cada etapa, explique em poucas linhas o objetivo, os conceitos e onde ela se encaixa.
2. Etapas pequenas. **Pare ao fim de cada etapa**, mostre o que mudou e como testar, e espere minha confirmação.
3. Simples, sem overengineering. Diferencie MVP, melhoria futura e desnecessário agora (seção 6).
4. Deixe uma parte pequena para eu escrever (Etapa 0) e revise depois, explicando os erros.
5. Só faça commit, push ou merge se eu pedir. Se eu pedir commit estando em `main`, crie uma branch antes.
6. Escrita em português do Brasil, **sem travessão** (use vírgula, dois-pontos ou espaço). Emoji só para identificação visual rápida.
7. Comandos de terminal que me passar: PowerShell em linha única, separados por `;`, nunca `&&`, explicação mínima. Use sempre `.venv\Scripts\python.exe`.
8. Não toque em `app/`, `docs/architecture.md`, `docs/data-model.md`, `docs/roadmap.md` nem no `.env.example` antigo de versão abandonada (o `.env.example` da raiz **pode** receber o comentário da seção 5, Etapa 3).
9. **Nunca leia, imprima, copie ou comite o conteúdo de um `.env` real**, `frontend/data/`, `data/`, `browser_profile/` ou `debug_snapshots/`. Nunca escreva token ou senha reais em arquivo versionado, teste ou log. Nos testes use valores falsos como `td_token_falso_123`.

## 3. Decisões de desenho (já fechadas, não reabrir)

- **Onde guardar:** no próprio `.env` da raiz (já ignorado pelo git e já lido pelo `_config_painel`). Nada de arquivo novo, banco, keyring ou criptografia.
- **O token só entra:** o navegador envia URL e token uma vez ao servidor local, que grava no `.env`. Nenhuma rota devolve o token, nenhum log o imprime, ele não vai para `localStorage`, `sessionStorage`, cookie nem para `os.environ`. A decisão antiga "o token fica só no servidor local, nunca no navegador" continua valendo no sentido de que ele nunca é guardado nem devolvido ao navegador.
- **Token em branco = manter o atual.** Assim dá para trocar só a URL sem colar o token de novo. Se não houver token atual e o campo vier em branco, erro claro.
- **Sem reiniciar.** Como `_config_painel` lê o `.env` a cada chamada, vale na hora.
- **Variável de ambiente ganha do `.env`** (comportamento atual do `_config_painel`). Se `PAINEL_URL` ou `PAINEL_TOKEN` existirem no ambiente do Windows, o valor gravado no `.env` seria ignorado em silêncio. A rota deve **avisar** isso na resposta.
- Reaproveitar `somente_painel` na nova rota de escrita.

## 4. Verificações antes de escrever código

Faça e me conte o resultado em poucas linhas:

1. `git status` e a branch atual. Garanta que `.env`, `data/` e `frontend/data/` estão ignorados (`git check-ignore -v`).
2. Em `techdrop_server.py`, confirme em qual host o `uvicorn.run` escuta. Esta rota grava um segredo no disco: se estiver em `0.0.0.0` em vez de `127.0.0.1`, **pare e me avise** antes de continuar.
3. Confirme no `python-dotenv` instalado no `.venv` que `set_key` **cria** o arquivo quando ele não existe, preserva as outras linhas e comentários, e como se comporta com `quote_mode="never"` e `encoding="utf-8"`. Prefiro o `.env` no estilo do `.env.example` (sem aspas). Valide com `dotenv_values` que o valor volta idêntico.
4. Rode a suíte atual (`.venv\Scripts\python.exe -m pytest -q`) e anote quantos testes passam antes de mexer, como linha de base.

## 5. Etapas

### Etapa 0: a minha parte (eu escrevo, você revisa)

Peça para eu escrever `_validar_token_painel(token: str) -> str | None` em `techdrop_server.py`, logo abaixo de `_validar_url_painel`, no mesmo padrão (devolve a mensagem de erro em português, ou `None` se serve). Regras para eu seguir:

- não pode ser vazio depois do `strip()`;
- não pode ter espaço nem quebra de linha (quebraria a linha do `.env` e o header `Authorization`, e seria um jeito de injetar outra variável no arquivo);
- opcional: prefixo `td_`. Antes de decidir, o Claude Code deve conferir em `painel_online` como o token é gerado, para não recusar token válido.

**Pare e espere eu colar o código.** Revise: aponte erros, explique o porquê, e só então ajuste ou use a minha versão. Se eu já tiver colado o código junto com este prompt, revise e siga.

### Etapa 1: backend (rota + gravação + testes)

Objetivo: `POST /api/painel/config` que valida e grava no `.env`.

- Modelo `ConfigPainelBody` com `url: str = ""` e `token: str = ""`. **Os dois com default**, e a validação é toda nossa. Motivo: o erro 422 padrão do FastAPI repete o corpo recebido no campo `input`, o que devolveria o token ao navegador. Garanta também que **nenhum caminho de erro** (400, 422, 500) contenha o token na resposta.
- `url`: `strip()` e `rstrip("/")`, depois `_validar_url_painel`. Erro: HTTP 400 com a mensagem.
- `token`: se vier preenchido, `strip()` e `_validar_token_painel`. Se vier em branco, reutilize o token atual de `_config_painel()`; se não houver, HTTP 400 ("Informe o token...").
- Gravar com `dotenv.set_key` as duas chaves em `ENV_FILE` (`PAINEL_URL`, `PAINEL_TOKEN`), em UTF-8, sem aspas, preservando o resto do arquivo. Sem tocar em `os.environ`.
- Resposta de sucesso: `{"configurado": True, "url": <url>, "aviso": <str|None>}`. `aviso` preenchido se `os.environ` tiver `PAINEL_URL` ou `PAINEL_TOKEN` (dizendo qual e que ela sobrepõe o `.env`, e como remover). **Sem o token.**
- Falha ao gravar (permissão, disco): HTTP 500 com mensagem clara em português, sem vazar caminho completo nem o valor.
- Não mude `/api/painel/status`.

Testes (adicione em `tests/test_painel_local_etapa4.py`, seção nova "configuração pelo painel", para reaproveitar as fixtures; cada um com valores falsos):

- grava as duas chaves, cria o `.env` quando não existe, e `GET /api/painel/status` passa a mostrar `configurado: True` e a URL;
- **preserva** linhas e comentários que já existiam no `.env`;
- a resposta, o status e o corpo de qualquer erro **não contêm o token**;
- o token **não** aparece em `os.environ` depois de gravar;
- token em branco mantém o anterior; em branco sem anterior dá 400;
- URL `http://` em host remoto dá 400 e **não grava nada** (o `.env` fica igual);
- token com espaço ou quebra de linha dá 400 e não grava (teste de injeção: `"td_x\nOUTRA=1"`);
- sem o header `X-TechDrop` a rota recusa (siga o que `somente_painel` já devolve);
- `aviso` aparece quando `PAINEL_URL` está no ambiente (`monkeypatch.setenv`);
- ida e volta: configurar pela rota usando o `online` e em seguida `POST /api/painel/enviar` funcionar de ponta a ponta.

Rode a suíte inteira. Mostre o resultado, compare com a linha de base e **pare**.

### Etapa 2: frontend (botão, janela, troca da mensagem de erro)

Objetivo: usar a rota da Etapa 1 sem editar arquivo.

- Botão "Configurar envio" ao lado do `btnPainel` no topo, no mesmo estilo visual. Sem emoji decorativo.
- Janela (`painelModal`) no padrão visual dos modais existentes, com:
  - campo URL (`type="url"`), preenchido com `painel.url` quando existir;
  - campo token (`type="password"`, `autocomplete="off"`), **sempre vazio ao abrir**; se `painel.configurado`, placeholder "já definido, deixe em branco para manter";
  - texto curto de ajuda: a URL começa com `https://` e o token é gerado no painel online, em "Meus tokens";
  - botões Salvar e Cancelar.
- Salvar chama `api('/api/painel/config', {url, token})`. Em sucesso: limpar o campo do token, fechar, `await carregarPainelStatus()`, `toast` de confirmação; se vier `aviso`, mostrar com tempo maior. Em erro: manter a janela aberta, mostrar a mensagem sem fechar e **sem apagar a URL digitada**.
- Limpar o campo do token também ao cancelar e ao fechar com Escape. Atualizar o handler de Escape existente para a nova janela, sem quebrar o comportamento atual.
- Em `enviarAoPainel()`, quando `!painel.configurado`, **abrir a janela** em vez de mostrar o toast antigo.
- O token não pode ir para `localStorage`, `sessionStorage`, nem para `console.log`.
- Siga o padrão de código do `app.js` (helpers `$`, `api`, `toast`). Nada de framework novo.

Valide no navegador com a skill de browser, **sem usar dados reais**: faça backup de `frontend/data/ofertas.json` antes, suba o painel local com `frontend\iniciar_teste.bat` (ou equivalente), e use um `.env` temporário. Se tiver que apontar `ENV_FILE`, faça isso só para o teste e restaure tudo depois. Cheque: janela abre pelo botão e pelo clique em "Enviar ao painel" sem config; erro de URL aparece sem fechar; salvar funciona; reabrir mostra a URL e o token vazio; Escape fecha e limpa. Mostre o que mudou e **pare**.

### Etapa 3: testes finais, docs e fechamento

- Suíte completa com `.venv\Scripts\python.exe -m pytest -q` e o resultado na tela.
- Confirme instalando num venv limpo que nada novo precisa entrar em `requirements.txt` (`python-dotenv` já está; o do servidor online é `requirements-painel.txt`, sem Playwright, e esta mudança é só do painel local).
- Escreva `docs/aprendizados/etapa-N.md`, onde N é o próximo número depois do último em `docs/aprendizados/` (confira também `docs/estrutura-do-projeto.md`; se houver dúvida, pergunte). Linguagem simples, no estilo dos arquivos anteriores. Inclua: por que gravar no `.env` e não em arquivo novo, por que `dotenv_values` e não `load_dotenv`, o risco de injeção no `.env` por quebra de linha, por que os campos têm default (eco do 422), e por que variável de ambiente ganha do `.env`.
- Atualize `docs/compartilhamento-de-dados.md`: nos passos de configuração (hoje "copie o `.env`...") acrescente o caminho pelo botão "Configurar envio" como forma principal e o `.env` como alternativa; atualize a linha da tabela de erros "Envio não configurado"; ajuste o glossário se citar o `.env`. Atualize também `docs/estrutura-do-projeto.md` se ele listar rotas ou arquivos afetados, e `frontend/README.md` se descrever o botão de envio.
- Em `.env.example`, acrescente uma linha de comentário dizendo que também dá para configurar pelo botão "Configurar envio" do painel, sem mexer nos exemplos existentes.
- Mostre `git status` e o resumo do que mudou. **Não faça commit.**

## 6. MVP, melhoria futura, desnecessário

- **MVP (esta tarefa):** rota de config, janela com URL e token, gravação no `.env`, aviso de variável de ambiente, testes, docs.
- **Melhoria futura (não faça agora, só liste no final):** botão "Testar conexão" que chama o `/api/saude` do painel online antes de salvar; botão "Remover configuração"; mostrar os últimos 4 caracteres do token para eu conferir qual está salvo.
- **Desnecessário agora:** criptografar o token no `.env`, usar keyring do Windows, vários perfis de painel, login no painel local, salvar a configuração no banco.

## 7. Definição de pronto

- Pelo painel, consigo salvar URL e token, enviar ofertas logo em seguida e nunca preciso reiniciar.
- Nenhuma resposta da API, log ou arquivo versionado contém o token.
- Todos os testes antigos continuam passando e os novos cobrem os casos da Etapa 1.
- `CLAUDE.md` respeitado: aprendizado escrito, docs atualizados, sem commit sem eu pedir.
- No fim, me diga em 3 linhas: o que mudou, como eu testo com meu token real (eu mesmo faço esse teste final, você não usa meus dados reais) e qual a próxima melhoria sugerida.
