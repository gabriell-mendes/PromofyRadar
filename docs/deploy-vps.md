# Deploy do painel online no VPS (Hostinger)

Roteiro para colocar o painel online no ar, com HTTPS, no seu VPS. Faça na ordem. Cada passo termina com uma **conferência**: só avance quando ela passar.

Convenções:
- `PC>` roda no **seu computador**, em PowerShell.
- `VPS$` roda no **servidor**, em Linux (Ubuntu).
- Troque `IP_DO_VPS` pelo IP do servidor e `painel.seudominio.com` pelo seu endereço.

## 0. O que você precisa antes

| Item | Detalhe |
|---|---|
| VPS | Hostinger KVM com Ubuntu 22.04 ou 24.04 (o Python precisa ser 3.10 ou mais novo) |
| Domínio | Um endereço seu, ex: `painel.seudominio.com`, com acesso para criar um registro DNS |
| Código no GitHub | O repositório `gabriell-mendes/grupo-de-ofertas` com o `main` atualizado (ver abaixo) |
| No PC | PowerShell com `ssh` (já vem no Windows 10/11) |

### Atenção: o servidor baixa o `main` do GitHub

O servidor clona o `main`. As etapas 1 a 6 já estão lá (`painel_online/`, `deploy/`, `historico.py`, `requirements-painel.txt`, `.gitattributes`). Confira que o seu PC não tem nada pendente que o servidor precise:

```powershell
cd C:\dev-docs\projects\grupo-de-ofertas; git fetch origin; git status -sb; git log origin/main --oneline -3
```

A primeira linha do `git status` não pode dizer `ahead` (commits seus que ainda não foram enviados). Se disser, envie o que for do painel com `git push` antes de seguir. **Sem o `historico.py` no GitHub o painel online não sobe.**

Nunca envie o `.env`, a pasta `data/` nem arquivos `.db` (o `.gitignore` já bloqueia, mas confira o `git status` antes).

## 1. Como as peças se encaixam

```
Internet --HTTPS (443)--> Caddy --> painel (127.0.0.1:8000) --> SQLite (/var/lib/painel/painel.db)
                          |                |
                  certificado         só ouve em localhost:
                  automático          não dá para acessar de fora
```

- **Caddy**: recebe a internet, cuida do certificado HTTPS sozinho e repassa ao painel. Também limita o tamanho do corpo (1 MB).
- **painel**: o FastAPI, rodando como serviço do sistema (systemd). Reinicia sozinho se cair e sobe com o servidor.
- **Três usuários do Linux, de propósito**: `root` (só no início), `deploy` (você, administra e atualiza o código) e `painel` (só roda o serviço e só consegue gravar em `/var/lib/painel`). Se alguém invadir o painel, não consegue mexer no código nem no sistema.
- **Firewall**: só portas 22 (SSH), 80 e 443 abertas.

## 2. Primeiro acesso e usuário não-root

No PC, entre no servidor como root (a senha ou chave vem no painel da Hostinger):

```powershell
ssh root@IP_DO_VPS
```

Atualize o sistema e crie o usuário `deploy` (o `adduser` pede uma senha: use uma forte, ela será usada no `sudo`):

```bash
apt update && apt upgrade -y
adduser deploy
usermod -aG sudo deploy
```

**No PC**, gere uma chave SSH (se ainda não tiver uma) e instale a parte pública no usuário `deploy`. Aceite os padrões do `ssh-keygen`:

```powershell
ssh-keygen -t ed25519 -C "meu-pc"
```

```powershell
$k = (Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub -Raw).Trim(); ssh root@IP_DO_VPS "install -d -m 700 -o deploy -g deploy /home/deploy/.ssh && echo '$k' >> /home/deploy/.ssh/authorized_keys && chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys"
```

**Conferência (em OUTRA janela do PowerShell, sem fechar a do root):**

```powershell
ssh deploy@IP_DO_VPS
```

Tem que entrar **sem pedir a senha do servidor** (se pedir a frase da chave, é a da chave). Depois rode `sudo whoami`: deve responder `root`.

Só agora, na janela do `deploy`, bloqueie o login do root e por senha. O arquivo começa com `00` para valer antes dos outros:

```bash
printf 'PermitRootLogin no\nPasswordAuthentication no\n' | sudo tee /etc/ssh/sshd_config.d/00-painel.conf
sudo sshd -t && sudo systemctl reload ssh
sudo sshd -T | grep -E "^(permitrootlogin|passwordauthentication)"
```

A última linha deve mostrar `permitrootlogin no` e `passwordauthentication no`. **Antes de fechar a janela do root**, teste em uma terceira janela que `ssh deploy@IP_DO_VPS` ainda entra.

> Se algo der errado e você ficar sem acesso: o painel da Hostinger (hPanel) tem um **terminal no navegador** para o VPS. É a sua rede de segurança.

A partir daqui tudo é como `deploy`.

## 3. Firewall

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Conferência: `Status: active` e só 22, 80 e 443 liberadas. A ordem importa: o SSH é liberado **antes** de ligar o firewall.

Se você ativou o firewall do hPanel da Hostinger, libere lá também 22, 80 e 443.

Recomendado (um comando): bloqueia quem erra a senha do SSH muitas vezes.

```bash
sudo apt install -y fail2ban
```

## 4. Domínio (registro A)

No lugar onde o DNS do domínio é gerenciado (hPanel da Hostinger, se o domínio está lá, ou no registrador), crie:

| Tipo | Nome | Valor |
|---|---|---|
| A | `painel` | `IP_DO_VPS` |

Conferência, no PC (pode levar de poucos minutos a algumas horas):

```powershell
nslookup painel.seudominio.com
```

Tem que mostrar o IP do VPS. **Não passe do passo 10 sem isso**: o Caddy só consegue o certificado se o domínio já apontar para o servidor.

## 5. Python, git e o código

```bash
sudo apt install -y python3 python3-venv python3-pip git
python3 --version
```

Conferência: versão 3.10 ou maior.

O repositório é privado, então o servidor precisa de uma **chave de deploy** (só leitura):

```bash
ssh-keygen -t ed25519 -C "vps-painel-deploy" -f ~/.ssh/id_github_deploy -N ""
cat ~/.ssh/id_github_deploy.pub
```

Copie a linha que aparece. No GitHub: repositório → **Settings** → **Deploy keys** → **Add deploy key**. Dê o título `VPS painel`, cole a chave e **deixe "Allow write access" desmarcado**.

```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/id_github_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
chmod 600 ~/.ssh/config
ssh -T git@github.com
```

Na primeira vez o SSH pergunta se confia no GitHub e mostra uma impressão digital. **Compare com a oficial** antes de digitar `yes`:

```
SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU
```

(Lista oficial: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints.) A conferência passa quando aparecer `Hi gabriell-mendes/grupo-de-ofertas! You've successfully authenticated`.

Agora clone:

```bash
sudo mkdir /opt/grupo-de-ofertas && sudo chown deploy:deploy /opt/grupo-de-ofertas
git clone git@github.com:gabriell-mendes/grupo-de-ofertas.git /opt/grupo-de-ofertas
ls /opt/grupo-de-ofertas/painel_online /opt/grupo-de-ofertas/deploy
```

Conferência: as duas pastas listam arquivos. Se `painel_online` não existir, o código novo não foi enviado ao GitHub (volte ao passo 0).

## 6. Ambiente virtual e dependências

```bash
cd /opt/grupo-de-ofertas
python3 -m venv venv
venv/bin/pip install -r requirements-painel.txt
venv/bin/pip list
```

Conferência: aparecem `fastapi`, `uvicorn`, `bcrypt`. **Não** deve ter `playwright` nem `requests`: o servidor não coleta nada, só recebe.

## 7. Usuário do serviço e pasta do banco

```bash
sudo adduser --system --group --no-create-home --shell /usr/sbin/nologin painel
sudo install -d -o painel -g painel -m 750 /var/lib/painel
sudo usermod -aG painel deploy
```

O último comando deixa o `deploy` ler os backups (para copiá-los). Vale depois de sair e entrar de novo no SSH.

## 8. Serviço systemd

```bash
sudo cp /opt/grupo-de-ofertas/deploy/painel.service /etc/systemd/system/painel.service
sudo systemctl daemon-reload
sudo systemctl enable --now painel
sudo systemctl status painel --no-pager
curl http://127.0.0.1:8000/api/saude
```

Conferência: `active (running)` e a resposta `{"ok":true}`.

Se não subir, veja o motivo:

```bash
sudo journalctl -u painel -n 50 --no-pager
```

## 9. Primeiro administrador

A senha é pedida no terminal (mínimo 10 caracteres; não aparece enquanto você digita). Use um gerenciador de senhas.

```bash
cd /opt/grupo-de-ofertas && sudo -u painel env PAINEL_DB=/var/lib/painel/painel.db venv/bin/python -m painel_online.cli criar-admin SEU_NOME
```

Conferência: `Administrador 'SEU_NOME' criado.` Para criar outros administradores, repita com outro nome. Quem esquecer a senha usa `redefinir-senha NOME` no mesmo formato.

## 10. Caddy (HTTPS)

Instalação oficial (fonte: https://caddyserver.com/docs/install):

```bash
sudo apt install --yes debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Use a nossa configuração, trocando o domínio (o `nslookup` do passo 4 já tem que ter passado):

```bash
sudo cp /opt/grupo-de-ofertas/deploy/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/painel.SEUDOMINIO.com/painel.seudominio.com/' /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Conferência, no PC:

```powershell
curl.exe -i https://painel.seudominio.com/api/saude
```

Tem que responder `200` com `{"ok":true}`, sem aviso de certificado. Abra `https://painel.seudominio.com` no navegador: aparece o login. Entre com o admin do passo 9.

Se o certificado não sair: veja `sudo journalctl -u caddy -n 50 --no-pager`. As causas comuns são o DNS ainda não ter propagado e as portas 80/443 bloqueadas (firewall do hPanel).

**Conferência de segurança, no PC:** o painel não pode estar acessível direto pela porta 8000.

```powershell
Test-NetConnection IP_DO_VPS -Port 8000
```

`TcpTestSucceeded` precisa ser `False`.

## 11. Backup diário

```bash
sudo cp /opt/grupo-de-ofertas/deploy/painel.cron /etc/cron.d/painel
sudo chown root:root /etc/cron.d/painel && sudo chmod 644 /etc/cron.d/painel
cd /opt/grupo-de-ofertas && sudo -u painel env PAINEL_DB=/var/lib/painel/painel.db venv/bin/python -m painel_online.backup
ls -l /var/lib/painel/backups
```

Conferência: o teste manual imprime `backup ok` e aparece um arquivo em `backups/`. O cron roda todo dia às 03:15 e guarda os 14 mais recentes; o resultado fica em `/var/lib/painel/backup.log`.

**O backup está no mesmo disco do servidor.** Se o VPS for perdido, ele vai junto. Copie para o seu PC de vez em quando (ex: toda semana):

```powershell
New-Item -ItemType Directory -Force C:\backups-painel | Out-Null; scp "deploy@IP_DO_VPS:/var/lib/painel/backups/*" C:\backups-painel\
```

(A Hostinger também oferece snapshots/backups do VPS inteiro no hPanel. Vale ligar.)

### Restaurar um backup

```bash
sudo systemctl stop painel
sudo rm -f /var/lib/painel/painel.db-wal /var/lib/painel/painel.db-shm
sudo cp /var/lib/painel/backups/painel-AAAA-MM-DD-HHMMSS.db /var/lib/painel/painel.db
sudo chown painel:painel /var/lib/painel/painel.db
sudo systemctl start painel
curl http://127.0.0.1:8000/api/saude
```

## 12. Teste de ponta a ponta (Etapa 7, rodada real)

O teste automático (`tests/test_painel_online_etapa7.py`) já prova a lógica com dois PCs simulados. Esta rodada prova a mesma coisa no servidor de verdade, com HTTPS.

**Parte A: um PC.**

1. No navegador, entre em `https://painel.seudominio.com` e vá em **Meus tokens**. Gere um token para o seu PC e copie na hora.
2. No PC, edite o `.env` na raiz do projeto:
   ```
   PAINEL_URL=https://painel.seudominio.com
   PAINEL_TOKEN=td_o_token_copiado
   ```
3. Reinicie o painel local (`frontend\iniciar.bat`), selecione uma oferta e clique em **Enviar ao painel**.
4. Atualize o painel online: a oferta aparece com o seu nome em "Enviado por".

> Testar o envio grava `enviado_painel_em` em `frontend/data/ofertas.json` (dados reais). Faça uma cópia do arquivo antes e restaure depois, se não quiser que essas ofertas fiquem marcadas como enviadas.

**Parte B: dois usuários, o mesmo produto.** Peça a uma segunda pessoa (ou crie um segundo usuário de teste com o passo 9 e use outro PC ou outra pasta do projeto com um `.env` próprio).

1. Cada um gera o **próprio** token e usa no `.env` do seu PC.
2. Os dois enviam o **mesmo produto** (o mesmo código `MLB...` no link), com preços diferentes.
3. No painel online: só **uma** oferta desse produto, com o preço do último envio e "Enviado por" igual a quem enviou por último.
4. Conferência no servidor, que mostra o histórico dos dois preços com o autor certo:
   ```bash
   sudo -u painel sqlite3 /var/lib/painel/painel.db "SELECT o.id_produto, p.preco, u.nome FROM precos p JOIN ofertas o ON o.id=p.oferta_id JOIN usuarios u ON u.id=p.enviado_por ORDER BY p.id DESC LIMIT 10;"
   ```
   (Se o `sqlite3` não estiver instalado: `sudo apt install -y sqlite3`.)
5. Saia da conta no navegador e abra `https://painel.seudominio.com/`: tem que redirecionar para `/login`.

Se tudo bateu, a Etapa 7 está fechada também no servidor.

## 13. Atualizar o painel depois

Quando o código mudar no GitHub (você faz `git push` do PC), no servidor, como `deploy`:

```bash
bash /opt/grupo-de-ofertas/deploy/atualizar.sh
```

Ele baixa a versão nova, atualiza as dependências, reinicia o painel e confere `/api/saude`. O banco fica em `/var/lib/painel`, fora do código, então atualizar não mexe nos dados.

## 14. Problemas comuns

| Sintoma | Causa provável | Correção |
|---|---|---|
| `502 Bad Gateway` no navegador | O serviço `painel` caiu | `sudo systemctl status painel` e `sudo journalctl -u painel -n 50 --no-pager` |
| Caddy não emite certificado | DNS não aponta para o IP, ou portas 80/443 bloqueadas | Refaça o `nslookup`, confira `ufw status` e o firewall do hPanel |
| Login "não pega" (volta ao login) | Acessando por `http` ou IP: o cookie é `Secure` e só vale em HTTPS | Use sempre `https://painel.seudominio.com` |
| `ModuleNotFoundError: historico` ao subir | `historico.py` não foi enviado ao GitHub | Envie, depois `bash deploy/atualizar.sh` |
| `unable to open database file` | A pasta do banco não é do usuário `painel` | `sudo chown -R painel:painel /var/lib/painel` |
| `pip install` falha por versão | Python anterior a 3.10 | Use a imagem Ubuntu 22.04 ou 24.04 |
| `Permission denied (publickey)` no `git clone` | Chave de deploy não cadastrada no GitHub | Refaça a parte da chave no passo 5 |
| Envio do PC: "O painel recusou o token" | Token errado ou revogado | Gere outro em Meus tokens |
| Envio do PC: "Não consegui conectar" | `PAINEL_URL` errado ou painel fora do ar | Teste `curl.exe https://painel.seudominio.com/api/saude` |

## 15. Checklist final de segurança

- [ ] Login por SSH só com chave, sem root (passo 2).
- [ ] Firewall ativo com 22, 80 e 443 (passo 3).
- [ ] Porta 8000 inacessível de fora (conferência do passo 10).
- [ ] Acesso ao painel só por `https://`.
- [ ] Nenhum `.env`, token ou senha no GitHub.
- [ ] Backup rodando e uma cópia fora do servidor.
- [ ] Chave de deploy do GitHub sem permissão de escrita.

## 16. MVP, melhoria futura, desnecessário

- **MVP:** tudo acima.
- **Melhoria futura:** monitoramento de disponibilidade (ex: UptimeRobot apontando para `/api/saude`), cópia automática do backup para fora do VPS, atualizações de segurança automáticas (`unattended-upgrades`), limite de tentativas de login por IP no Caddy (exige plugin).
- **Desnecessário agora:** Docker, vários servidores, balanceador, banco PostgreSQL.
