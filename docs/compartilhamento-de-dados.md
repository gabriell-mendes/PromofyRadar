# Compartilhamento de dados: painel online

Este guia explica como várias pessoas coletam ofertas no próprio computador e juntam tudo em um painel online compartilhado. Escrito para quem não conhece o código.

> Status: em construção, uma etapa por vez. A tabela abaixo mostra o que já está pronto.

| Etapa | O que é | Situação |
|---|---|---|
| 1 | Contrato da oferta (`OfertaIn`) e regra "novo ou atualização" | Pronta |
| 2 | Painel online mínimo (FastAPI + SQLite) | Pronta |
| 3 | Login web e tokens de API | Pronta |
| 4 | Botão "Enviar ao painel" no painel local | Pronta |
| 5 | Deploy no VPS Hostinger | Arquivos e roteiro prontos; falta executar no seu servidor |
| 6 | Guia por PC | Pronta |
| 7 | Teste de ponta a ponta | A fazer |

## 1. Visão geral

Cada pessoa roda o scraper no próprio PC (IP e navegador próprios), revisa as ofertas e envia as aprovadas para um painel online único. Todos os administradores veem tudo junto. O servidor online não roda scraper nem navegador: só recebe, guarda, deduplica e exibe.

```
PC do João                     PC da pessoa B
 scraper + painel local            scraper + painel local
        |                                  |
        |  HTTPS POST /api/ingest          |
        |  Authorization: Bearer <token>   |
        +----------------+-----------------+
                         v
                 PAINEL ONLINE (VPS)
                 FastAPI + SQLite
                         ^
                         |  login com usuário e senha
                         |  (cookie de sessão)
                 Administradores no navegador
```

## 2. O caminho de uma oferta

1. O scraper do seu PC coleta a oferta e grava em `frontend/data/ofertas.json`.
2. Você revisa no painel local e aprova.
3. O painel local envia as aprovadas ao painel online (`POST /api/ingest`) com o seu token.
4. O painel online valida cada oferta com o contrato `OfertaIn`.
5. Ele calcula o `id_produto` a partir do link (código `MLB...`) e consulta se `(loja, id_produto)` já existe.
6. Se não existe, cria (`novo`). Se existe, atualiza (`atualizacao`) e guarda o preço novo no histórico.
7. O servidor grava quem enviou, a partir do token. Esse campo nunca vem do cliente.
8. Os administradores entram no painel online com usuário e senha e veem as ofertas de todos, juntas.

Todos os passos já existem (Etapas 1 a 4). 
### Enviar ofertas do painel local ao painel online (Etapa 4)

Pré-requisito: você tem usuário no painel online (quem administra o servidor cria com `criar-admin`) e gerou um token em "Meus tokens".

**1. Configure o `.env`** (na raiz do projeto; copie de `.env.example` se não existir). O `.env` nunca vai para o git:

```
PAINEL_URL=https://painel.seudominio.com
PAINEL_TOKEN=td_cole_aqui_o_token_gerado
```

A URL precisa ser `https://` (só `localhost` pode ser `http`). Reinicie o painel local depois de editar o `.env`.

**2. Colete e revise** no painel local como sempre (aba Scraper, depois Produtos). Descarte o que não presta.

**3. Envie.** Duas formas:

- Marque as ofertas desejadas e clique em **Enviar ao painel** na barra de baixo, ou
- Clique em **Enviar ao painel (N)** no topo: manda todas as que ainda não foram enviadas (N é quantas faltam).

O painel mostra para qual endereço vai e pede confirmação. Ao terminar, aparece quantas foram criadas, atualizadas ou recusadas, e as enviadas ganham a etiqueta **NO PAINEL**.

**4. Confira** entrando no painel online: as ofertas aparecem com o seu nome em "Enviado por".

Detalhes que ajudam:

- Reenviar é seguro. O painel online não duplica: atualiza a oferta e soma uma linha no histórico de preços.
- Uma nova coleta do mesmo produto tira a etiqueta e ele volta a contar como pendente de envio.
- Ofertas de teste (do `iniciar_teste.bat`) nunca são enviadas.
- Só ofertas que estão no `ofertas.json` do painel local podem ser enviadas (as abertas por "Carregar JSON" não).
- O token fica só no servidor local. O navegador nunca o vê.

### Testar o painel online na sua máquina (Etapas 2 e 3)

Na raiz do projeto, em PowerShell.

**1. Criar o administrador** (a senha é pedida no terminal, com mínimo de 10 caracteres, e não aparece na tela):

```powershell
.venv\Scripts\python.exe -m painel_online.cli criar-admin seunome
```

**2. Subir o painel** em http://127.0.0.1:8000. O `PAINEL_COOKIE_SECURE=0` é só para testar em `http` na sua máquina. No servidor com HTTPS, não use:

```powershell
$env:PAINEL_COOKIE_SECURE = "0"; .venv\Scripts\python.exe -m uvicorn painel_online.app:app --port 8000
```

**3. Entrar e gerar o token do seu PC.** Abra http://127.0.0.1:8000, entre com usuário e senha, vá em "Meus tokens", dê um nome ao PC e clique em "Gerar token". Copie na hora: ele aparece uma única vez.

**4. Enviar uma oferta de teste**, em outro PowerShell (troque `SEU_TOKEN`):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/ingest -Headers @{ Authorization = "Bearer SEU_TOKEN" } -ContentType 'application/json' -Body (@{ ofertas = @(@{ loja = 'mercadolivre'; url = 'https://www.mercadolivre.com.br/x/p/MLB25171538'; titulo = 'Produto de teste'; preco = 99.9 }) } | ConvertTo-Json -Depth 5)
```

A resposta diz quantas ofertas foram `criadas`, `atualizadas` e `ignoradas` (com o motivo de cada ignorada). Enviar de novo o mesmo produto vira `atualizadas` e soma uma linha no histórico de preços. Atualize a página do painel para ver a oferta. O banco fica em `data/painel_online.db` (fora do git).

Regras do envio: no máximo 500 ofertas e 1 MB por pedido. `url` e `imagem` precisam começar com `http://` ou `https://`. O campo `enviado_por` nunca é aceito do cliente: vem do token.

**Esqueceu a senha?** No servidor, rode `.venv\Scripts\python.exe -m painel_online.cli redefinir-senha seunome`. Isso também derruba as sessões abertas desse usuário.

### Colocar o painel online no ar (administrador do servidor)

Quem vai hospedar segue o roteiro completo em [`docs/deploy-vps.md`](deploy-vps.md): usuário não-root, firewall, domínio, Python, clone do repositório privado, serviço systemd, Caddy com HTTPS, backup por cron e como atualizar depois.

## 3. Guia para rodar o scraper no seu PC

Este guia é para quem vai coletar ofertas no **próprio computador** e enviá-las ao painel online. Você não precisa saber programar: copie e cole os comandos, na ordem.

Testado numa instalação limpa: dependências, painel local, coleta de teste, `.env`, envio ao painel online e conferência. O download do navegador do coletor segue o comando oficial do Playwright e não foi baixado nesse teste.

### O que você vai fazer, em resumo

1. Instalar o projeto no seu PC (uma vez).
2. Colocar o seu token no `.env` (uma vez).
3. Coletar ofertas, revisar e enviar (sempre que quiser).

A coleta roda no **seu** computador, com a **sua** internet e o **seu** navegador. O painel online nunca coleta nada: só recebe o que você aprovou.

### Pré-requisitos

| O que | Como conseguir |
|---|---|
| Windows 10 ou 11 | Os atalhos `.bat` do guia são para Windows |
| Python 3.10 ou mais novo | Baixe em python.org. Na instalação, marque **Add python.exe to PATH** |
| Git | Baixe em git-scm.com e instale com as opções padrão |
| Acesso ao repositório | Peça ao administrador para convidar o seu usuário do GitHub e aceite o convite que chega por e-mail (o repositório é privado) |
| Usuário no painel online | O administrador cria e te passa o usuário e a senha |
| Cerca de 500 MB livres | O navegador do coletor e as dependências ocupam esse espaço |

Para conferir o Python, abra o PowerShell e rode `python --version`: tem que aparecer 3.10 ou maior.

### Instalação (uma vez só)

Tudo no PowerShell. O primeiro comando baixa o projeto (o Git abre o navegador para você entrar no GitHub):

```powershell
cd $env:USERPROFILE; git clone https://github.com/gabriell-mendes/grupo-de-ofertas.git; cd grupo-de-ofertas
```

Cria o ambiente do projeto e instala as dependências (leva alguns minutos):

```powershell
python -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt
```

Baixa o navegador que o coletor usa (cerca de 150 MB):

```powershell
.venv\Scripts\python.exe -m playwright install chromium
```

### Configurar o envio (uma vez só)

**1. Gere o seu token.** Entre no painel online com o seu usuário e senha, vá em **Meus tokens**, dê um nome ao PC (ex: `PC do Carlos`) e clique em **Gerar token**. Copie na hora: ele aparece uma única vez. Cada pessoa, e cada PC, usa um token próprio.

**2. Crie o arquivo `.env`** e abra no Bloco de Notas:

```powershell
Copy-Item .env.example .env; notepad .env
```

No fim do arquivo estão duas linhas que começam com `# `. **Apague o `# `** das duas e preencha com os seus valores:

```
PAINEL_URL=https://painel.seudominio.com
PAINEL_TOKEN=td_cole_aqui_o_seu_token
```

Salve e feche. O `.env` é só seu: o Git o ignora, e ele **nunca** deve ser enviado nem compartilhado.

### Usar no dia a dia

**1. Abra o painel local.** Dê dois cliques em `frontend\iniciar.bat` (ou rode `.\frontend\iniciar.bat` no PowerShell). Abre sozinho em http://localhost:5500. Deixe a janela preta aberta enquanto usa.

**2. Colete.** Na aba **Scraper**, escolha como buscar (por produto, por categoria ou pela aba de Ofertas), preencha os campos e clique em **Iniciar busca**. Uma janela do navegador abre sozinha e navega pelas páginas: **não feche nem use essa janela** até terminar. O terminal da tela mostra o andamento e termina com uma frase como `[TechDrop] 12 ofertas desta busca`. Comece com **1 a 3 páginas** (veja as regras de uso abaixo).

**3. Revise.** Clique em **Ver em Produtos**. Use os filtros (desconto, Deal Score, busca) e **Descarte** o que não vale a pena. Só envie o que você aprovaria publicar.

> Sobre o Deal Score: ele compara o preço com o histórico **do seu PC**. Nas primeiras coletas a confiança é "baixa" porque ainda não há histórico. Com o tempo ele melhora.

**4. Envie.** Duas formas:

- Marque as ofertas e clique em **Enviar ao painel** na barra de baixo, ou
- Clique em **Enviar ao painel (N)** no topo para mandar todas as que ainda não foram enviadas.

Confirme na janelinha (ela mostra para qual endereço vai). As enviadas ganham a etiqueta **NO PAINEL**.

**5. Confira no painel online.** Entre com o seu usuário: as ofertas aparecem com o seu nome em **Enviado por**.

**6. Ao terminar,** feche a janela preta do painel local.

### Atualizar o projeto

De vez em quando o código recebe melhorias. No PowerShell, dentro da pasta `grupo-de-ofertas`:

```powershell
git pull; .venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Testar sem navegador (opcional)

Dê dois cliques em `frontend\iniciar_teste.bat`. Ele usa coletores de mentira, sem abrir navegador nem acessar nenhuma loja, ótimo para conhecer a tela. Ofertas de teste têm a etiqueta **TESTE** e **nunca são enviadas** ao painel online.

### Para quem administra: preparar uma pessoa nova

1. No GitHub, no repositório: **Settings**, **Collaborators**, **Add people**. Dê permissão de **leitura** (basta para baixar e atualizar).
2. No servidor, crie o usuário dela (o comando está em `docs/deploy-vps.md`, passo 9) e envie a senha por um canal privado.
3. Peça que ela siga este guia, gerando o próprio token em **Meus tokens**.
4. Se ela esquecer a senha, use `redefinir-senha`. Se um PC for perdido, revogue só o token daquele PC.

## 4. Regras de uso do scraper

Estas regras valem para todo mundo que coleta. Elas protegem você, as lojas e o projeto.

**Coletar com educação**

- Uma busca por vez, no seu PC, com a sua internet. O painel já impede duas buscas ao mesmo tempo.
- Recomendação conservadora do projeto (não é um limite oficial de nenhuma loja): até **3 páginas por busca** e **pelo menos 10 minutos entre uma busca e outra**. Mais que isso aumenta a chance de bloqueio e traz pouco ganho.
- Não deixe coletas rodando em repetição automática. Coleta é uma ação sua, com revisão no fim.
- Colete só informação pública de oferta (título, preço, link, imagem). Nunca dados de pessoas.
- Leia e respeite os termos de uso das lojas. O uso é sua responsabilidade.

**Se a loja bloquear**

- Se aparecer erro 403, página de verificação, CAPTCHA, ou a coleta voltar de repente sem nenhuma oferta: **pare**. Não tente de novo na hora.
- Espere algumas horas e volte com menos páginas e mais intervalo.
- Avise o grupo: se o bloqueio se repetir para todo mundo, o caminho é a API oficial da loja ou coletar bem menos vezes.

**Cuidado com o que você envia**

- Envie só o que você revisou e aprovaria publicar. O painel online é a vitrine do grupo.
- Preços mudam rápido: envie logo depois de coletar.
- O token é seu, de um PC só. Não passe para ninguém, não cole em mensagens e nunca coloque em arquivos que vão para o GitHub. Se vazar, revogue em **Meus tokens** e gere outro.

**Cuidado com o seu PC**

- A pasta `browser_profile/` guarda o perfil do navegador do coletor. Ela é só sua: não compartilhe nem envie para o GitHub.
- Não edite os arquivos do projeto sem combinar com o administrador. Se algo quebrar, rode `git pull`.

## 5. Segurança

Existem **duas credenciais diferentes**, cada uma para um tipo de cliente:

| | Token de API | Cookie de sessão |
|---|---|---|
| Quem usa | O seu **PC**, ao enviar ofertas | O **administrador**, no navegador |
| Como nasce | Você gera em "Meus tokens" | Ao entrar com usuário e senha |
| Duração | Até ser revogado | 7 dias, ou até sair |
| Serve para | Só `POST /api/ingest` | Ver, descartar e restaurar ofertas, gerenciar tokens |
| Se vazar | Alguém consegue enviar ofertas como você. Não abre o painel | Alguém navega no painel como você. Não consegue enviar como PC |

O que o sistema faz por você:

- Senhas ficam em hash bcrypt: nem o dono do servidor vê a senha.
- Tokens e sessões ficam no banco só como hash (sha256): quem copiar o banco não consegue usá-los.
- O cookie é `HttpOnly` (o JavaScript da página não lê), `Secure` (só trafega por HTTPS) e `SameSite=Lax` (não vai em requisição disparada por outro site). As ações que mudam dados exigem também um header que outro site não consegue enviar (proteção CSRF).
- Após 5 senhas erradas seguidas, aquele usuário fica bloqueado por 10 minutos.
- O logout apaga a sessão no servidor: um cookie copiado antes deixa de valer.

**Se um token vazar:** entre no painel, vá em "Meus tokens" e clique em "Revogar" naquele token. O envio com ele passa a dar erro 401 na hora. Depois gere um novo e atualize o `.env` do PC.

**Se achar que sua senha vazou:** peça a quem administra o servidor para rodar `redefinir-senha` do seu usuário.

Os cuidados do servidor (HTTPS, firewall, usuário sem privilégios, backup) estão no roteiro [`docs/deploy-vps.md`](deploy-vps.md), que também traz o checklist final de segurança.

Resumo do que protege o servidor:

- O painel só escuta em `127.0.0.1:8000`; quem recebe a internet é o Caddy, com HTTPS automático.
- O serviço roda como um usuário sem login (`painel`), que só consegue gravar na pasta do banco.
- O firewall deixa abertas só as portas 22, 80 e 443, e o SSH aceita apenas chave.
- O servidor não tem Playwright nem scraper: só recebe e guarda.
- Backup diário do banco, com conferência de integridade; guarde também uma cópia fora do servidor.

## 6. Solução de problemas

| Sintoma | Causa provável | Correção |
|---|---|---|
| Painel redireciona para `/login` o tempo todo, mesmo logado | O cookie `Secure` não é enviado por `http` | Em teste local, suba com `PAINEL_COOKIE_SECURE=0`. No servidor, use HTTPS |
| "Usuário ou senha incorretos" | Nome ou senha errados (a mensagem é a mesma de propósito) | Confira o nome exato. Se esqueceu, `redefinir-senha` |
| "Muitas tentativas" (429) | 5 senhas erradas seguidas | Espere 10 minutos e tente de novo |
| Envio retorna 401 "Token inválido ou revogado" | Token errado, copiado incompleto ou revogado | Gere um token novo em "Meus tokens" |
| Painel local: "Envio não configurado" | `PAINEL_URL` ou `PAINEL_TOKEN` faltando no `.env`, ou o painel não foi reiniciado | Preencha o `.env` e reinicie o painel local |
| Painel local: "precisa começar com https://" | `PAINEL_URL` em `http` para um servidor remoto | Use o endereço `https://` |
| Painel local: "Não consegui conectar" | Sem internet, URL errada ou painel online fora do ar | Confira a internet e o `PAINEL_URL` |
| Painel local: "O painel recusou o token" | Token errado, copiado incompleto ou revogado | Gere um novo em Meus tokens e atualize o `.env` |
| Envio parou no meio ("Já chegaram N") | A conexão caiu durante o envio | Clique em enviar de novo: não duplica |
| Botão "Enviar ao painel" desativado | Não há ofertas pendentes (todas já enviadas) | Selecione ofertas e use o botão da barra de baixo para reenviar |
| Envio retorna 413 | Mais de 1 MB no pedido | Envie em lotes menores (até 500 ofertas) |
| PowerShell: `python não é reconhecido` | Python não instalado, ou sem PATH | Reinstale marcando **Add python.exe to PATH** e abra um PowerShell novo |
| `git clone` dá "Repository not found" | O convite do GitHub ainda não foi aceito | Peça o convite ao administrador, aceite pelo e-mail e tente de novo |
| `ModuleNotFoundError` ao abrir o painel | Dependências não instaladas, ou rodando fora do ambiente do projeto | Rode de novo `.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| Erro "Executable doesn't exist" ao coletar | Falta baixar o navegador do coletor | `.venv\Scripts\python.exe -m playwright install chromium` |
| "Já existe uma busca rodando" | Outra coleta ainda em andamento | Espere terminar ou clique em **Parar** |
| A coleta termina sem nenhuma oferta | Sem internet, página mudou ou bloqueio | Leia o terminal da aba Scraper. Se for 403 ou verificação, pare e siga as regras de uso |
| Porta 5500 em uso | Já existe um painel local aberto | Feche o outro, ou `$env:TECHDROP_PORT = "5501"; .\frontend\iniciar.bat` |
| Navegador mostra `502 Bad Gateway` | O serviço do painel no servidor caiu | No servidor: `sudo journalctl -u painel -n 50 --no-pager` (mais em `docs/deploy-vps.md`) |
| Envio retorna 422 | Lista vazia ou mais de 500 ofertas | Ajuste o tamanho do lote |
| Oferta aparece em `ignoradas` | Falhou na validação ou o produto foi descartado no painel | Veja o `motivo` em `detalhes_ignoradas` |
| `criar-admin` trava no PowerShell ao redirecionar a entrada | A senha é lida do teclado, não de pipe | Rode o comando direto e digite a senha |

## 7. Perguntas frequentes

**Preciso deixar alguma coisa ligada o tempo todo?**
Não. Só o painel local (a janela preta) enquanto você coleta e envia. O painel online fica ligado no servidor.

**Por que o Deal Score da mesma oferta é diferente em PCs diferentes?**
Porque cada PC calcula a nota com o histórico de preços que **ele mesmo** guardou. O painel online não recalcula: mostra a nota do último envio.

**Dois de nós enviamos o mesmo produto. O que acontece?**
Não duplica. O painel online guarda uma oferta só, com os dados do último envio, e o histórico de preços fica com os dois preços (cada um com quem enviou). O campo "Enviado por" mostra quem enviou por último.

**Posso enviar a mesma oferta mais de uma vez?**
Pode, é seguro. Ela é atualizada e soma uma linha no histórico de preços. Por isso o botão do topo manda só as que ainda não foram enviadas.

**Se eu descartar uma oferta no meu painel, ela some para os outros?**
Não. O descarte do **painel local** é só seu. O descarte feito no **painel online** vale para todos os administradores, e um produto descartado lá é ignorado se alguém reenviar.

**Consigo ver no painel local as ofertas dos outros?**
Não. Para ver tudo junto, entre no painel online.

**Perdi ou vazei meu token. E agora?**
No painel online, vá em **Meus tokens**, revogue o antigo e gere um novo. Depois troque o `PAINEL_TOKEN` no seu `.env`.

**Onde ficam os meus dados?**
No seu PC, nas pastas `data/` e `frontend/data/`, que o Git ignora. Só o que você envia vai para o painel online.

**Editei o `.env` e nada mudou.**
Recarregue a página do painel local (F5). Se continuar igual, feche a janela preta e abra o `iniciar.bat` de novo.

**Posso usar no Mac ou no Linux?**
Os atalhos `.bat` são do Windows. O projeto em si é Python e pode rodar em outros sistemas, mas este guia foi testado só no Windows.

**Quanto tempo leva uma coleta?**
Depende do número de páginas. Com 1 a 3 páginas costuma levar poucos minutos.

## 8. Glossário

| Termo | Significado |
|---|---|
| Oferta | Um produto com preço, desconto e Deal Score, coletado por um scraper |
| `OfertaIn` | O molde que define os campos de uma oferta enviada ao painel online |
| `id_produto` | Código estável do produto (ex: `MLB25171538`), extraído do link |
| Chave do produto | O par `(loja, id_produto)` que identifica um produto no painel |
| Upsert | Criar se não existe, atualizar se já existe |
| Ingest | Receber ofertas enviadas pelos PCs (`POST /api/ingest`) |
| Scraper (coletor) | Programa que visita as páginas da loja e lê título, preço e link das ofertas. Roda no seu PC |
| Chromium / Playwright | O navegador e a ferramenta que o coletor usa para abrir as páginas |
| venv (`.venv`) | Pasta com as dependências do projeto, separada do resto do seu PC |
| `.env` | Arquivo local com configurações e segredos (`PAINEL_URL`, `PAINEL_TOKEN`). Não vai para o git |
| Descartada | Oferta marcada como não aproveitável no painel online. Vale para todos os admins e não volta se for reenviada |
| Histórico de preços | Uma linha por envio (preço, data, quem enviou), usada para ver como o preço mudou |
| Token de API | Senha longa usada pelo PC para se identificar ao enviar ofertas. Não abre o painel |
| Sessão / cookie de sessão | O que prova no navegador que você entrou com usuário e senha. Vale 7 dias ou até sair |
| Revogar | Invalidar um token na hora, sem apagar o histórico dele |
| VPS | Servidor virtual alugado (aqui, da Hostinger) onde o painel online roda |
| Caddy | Programa que recebe a internet, cuida do HTTPS sozinho e repassa ao painel |
| systemd | O gerenciador de serviços do Linux: mantém o painel ligado e o reinicia se cair |
| bcrypt | Forma lenta e segura de guardar senhas: o banco nunca contém a senha, só uma impressão dela |
| CSRF | Ataque em que outro site tenta fazer seu navegador executar uma ação no painel usando seu cookie. O header exigido nas ações impede isso |
| Deal Score | Nota de 0 a 100 da oferta, calculada por regras e dados, nunca por opinião de IA |
