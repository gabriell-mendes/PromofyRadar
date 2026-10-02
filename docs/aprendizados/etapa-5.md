# Etapa 5: deploy no VPS

Resumo de conceitos para levar ao Obsidian.

## O que foi feito

| Item | Para que serve |
|---|---|
| `docs/deploy-vps.md` | Roteiro completo, em ordem, com uma conferência ao fim de cada passo |
| `requirements-painel.txt` | Só `fastapi`, `uvicorn` e `bcrypt`: o servidor não instala Playwright |
| `deploy/painel.service` | Serviço systemd do painel |
| `deploy/Caddyfile` | HTTPS automático, limite de corpo de 1 MB, repasse ao painel |
| `deploy/painel.cron` | Backup diário às 03:15 |
| `deploy/atualizar.sh` | `git pull`, dependências, reinício e conferência |
| `painel_online/backup.py` | Backup consistente do SQLite, com conferência e rotação |
| `GET /api/saude` | Resposta simples para conferir deploy e, no futuro, monitorar |
| `.gitattributes` | Garante fim de linha LF nos arquivos de `deploy/` (Windows quebraria o script no Linux) |
| `tests/test_painel_online_etapa5.py` | 12 testes |

**O que NÃO foi feito:** a execução no VPS. Isso depende do seu servidor, do domínio e do seu SSH, e não é algo que eu deva fazer por você. O roteiro foi escrito para você rodar, e a parte que dá para provar sem o servidor foi provada aqui.

## Conceitos

**Reverse proxy.** O painel não fica exposto à internet. Ele escuta só em `127.0.0.1:8000`; o Caddy recebe as conexões em 443, faz o HTTPS e repassa. Vantagens: certificado automático e renovado sozinho, limite de tamanho de corpo em um lugar só, e o app Python nunca fala direto com a internet.

**Menor privilégio com três usuários.** `root` só configura no começo. `deploy` administra e atualiza o código. `painel` roda o serviço e só grava em `/var/lib/painel`. Se o painel for invadido, o invasor não altera o código nem o sistema. O systemd reforça com `NoNewPrivileges`, `ProtectSystem=strict` e `ProtectHome`.

**Dados fora do código.** O banco fica em `/var/lib/painel`, não na pasta do repositório. Assim `git pull` e `atualizar.sh` nunca tocam nos dados, e o backup tem um único lugar para olhar.

**Firewall em camadas.** O `ufw` fecha tudo menos 22, 80 e 443. O painel ainda escuta só em localhost, então mesmo com firewall errado a porta 8000 não ficaria aberta. A conferência `Test-NetConnection ... -Port 8000` prova isso.

**SSH só com chave.** Senha pode ser adivinhada; chave não. A ordem é o ponto crítico: instalar a chave, **testar o login em outra janela** e só então desligar root e senha, senão você se tranca para fora. O arquivo de configuração começa com `00-` porque o SSH usa o primeiro valor que encontra, e arquivos do provedor (`50-...`) poderiam reativar a senha.

**Chave de deploy.** O repositório é privado, então o servidor precisa de uma credencial. Uma chave de deploy dá acesso a **um** repositório, só leitura. É bem mais segura do que colocar sua conta pessoal do GitHub no servidor. Na primeira conexão, compara-se a impressão digital do GitHub com a oficial para evitar um falso servidor.

**Backup de SQLite não é copiar arquivo.** Com o modo WAL, parte dos dados recentes está num arquivo à parte (`-wal`); copiar só o `.db` pode perder dados ou gerar uma cópia quebrada. O `Connection.backup()` do SQLite gera uma cópia consistente com o painel no ar. Um teste prova que dado ainda no WAL entra no backup. A cópia é conferida com `integrity_check` antes de valer, e backup velho é apagado (rotação).

**Backup no mesmo disco não basta.** Se o servidor for perdido, os backups vão junto. Por isso o roteiro manda copiar para o PC (`scp`) e sugere o snapshot do hPanel.

**Idempotência da atualização.** `atualizar.sh` usa `set -euo pipefail` (para no primeiro erro) e `git pull --ff-only` (nunca cria merge no servidor). Pode ser rodado quantas vezes quiser.

**Testes de coerência dos arquivos de deploy.** Um teste confere que a porta do serviço bate com a do Caddy, que o banco do serviço e do cron é o mesmo, que o limite do Caddy (1 MB) bate com o do app, e que o serviço nunca escuta em `0.0.0.0`. Erros de configuração entre arquivos são comuns e só apareceriam no servidor.

## Validado aqui

- Venv **limpo** só com `requirements-painel.txt`: nada de Playwright ou requests, 57 testes passam e o painel sobe como o serviço fará (`/api/saude`, redirecionamento de login, 401 sem sessão).
- Backup rodando pelo CLI sobre um banco real, gerando a cópia e a pasta `backups/`.

## Achado

O código novo (`painel_online/`, `historico.py`, `deploy/`) ainda não está no GitHub. Sem `historico.py` o painel online não sobe. O passo 0 do roteiro cobre isso.

## MVP, melhoria futura, desnecessário

- MVP: o que foi feito.
- Melhoria futura: monitoramento de disponibilidade, cópia automática do backup para fora do servidor, `unattended-upgrades`, limite de login por IP no Caddy (plugin), deploy automático por GitHub Actions.
- Desnecessário agora: Docker, vários servidores, Postgres, balanceador.
