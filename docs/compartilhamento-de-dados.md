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
| 6 | Guia por PC | A fazer |
| 7 | Teste de ponta a ponta | A fazer |

## 1. Visão geral

Cada pessoa roda o scraper no próprio PC (IP e navegador próprios), revisa as ofertas e envia as aprovadas para um painel online único. Todos os administradores veem tudo junto. O servidor online não roda scraper nem navegador: só recebe, guarda, deduplica e exibe.

```
PC do Gabriel                     PC da pessoa B
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

Será escrito na Etapa 6.

## 4. Regras de uso do scraper

Será escrito na Etapa 6. Princípio geral: respeitar os termos de uso das lojas e limitar a frequência. Se uma fonte bloquear, o caminho é API oficial ou coletar menos vezes, nunca contornar CAPTCHA ou anti-bot.

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
| Navegador mostra `502 Bad Gateway` | O serviço do painel no servidor caiu | No servidor: `sudo journalctl -u painel -n 50 --no-pager` (mais em `docs/deploy-vps.md`) |
| Envio retorna 422 | Lista vazia ou mais de 500 ofertas | Ajuste o tamanho do lote |
| Oferta aparece em `ignoradas` | Falhou na validação ou o produto foi descartado no painel | Veja o `motivo` em `detalhes_ignoradas` |
| `criar-admin` trava no PowerShell ao redirecionar a entrada | A senha é lida do teclado, não de pipe | Rode o comando direto e digite a senha |

## 7. Perguntas frequentes

Será preenchido ao longo das etapas.

## 8. Glossário

| Termo | Significado |
|---|---|
| Oferta | Um produto com preço, desconto e Deal Score, coletado por um scraper |
| `OfertaIn` | O molde que define os campos de uma oferta enviada ao painel online |
| `id_produto` | Código estável do produto (ex: `MLB25171538`), extraído do link |
| Chave do produto | O par `(loja, id_produto)` que identifica um produto no painel |
| Upsert | Criar se não existe, atualizar se já existe |
| Ingest | Receber ofertas enviadas pelos PCs (`POST /api/ingest`) |
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
