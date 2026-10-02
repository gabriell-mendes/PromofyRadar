# Etapa 3: login web e tokens de API

Resumo de conceitos para levar ao Obsidian.

## O que foi feito

| Arquivo | Papel |
|---|---|
| `credenciais.py` | Regras de senha e bcrypt (`hash_senha`, `verificar_senha`) |
| `auth.py` | Token (PCs), sessão por cookie (admins), proteção CSRF, limite de tentativas de login |
| `db.py` | Tabela `sessoes`, `criar_usuario`, `redefinir_senha`, `criar_token` |
| `app.py` | `/login`, `/api/login`, `/api/logout`, `/api/eu`, `/api/tokens`, páginas protegidas |
| `cli.py` | `criar-admin NOME` e `redefinir-senha NOME` (senha pedida no terminal) |
| `paginas/` e `static/comum.js` | Telas de login, ofertas e "Meus tokens" |

## Conceitos

**Token de API vs cookie de sessão.** São credenciais para clientes diferentes. O token é a chave do **PC**: vai em `Authorization: Bearer`, não expira sozinho, só serve em `POST /api/ingest`. O cookie é a pulseira do **administrador no navegador**: nasce no login, expira, e o navegador o envia sozinho. Separar limita o estrago: token vazado não abre o painel, cookie roubado não forja envio de PC. Dois testes garantem a separação nos dois sentidos.

**Hash de senha com bcrypt.** Nunca se guarda a senha, só uma impressão dela. bcrypt é lento de propósito e embute um "sal" aleatório, então senhas iguais geram hashes diferentes e força bruta é cara. Limite de 72 bytes é do próprio bcrypt, por isso a regra de senha de 10 a 72 bytes.

**sha256 para token, bcrypt para senha.** Token tem 256 bits aleatórios: impossível de adivinhar, então um hash rápido basta. Senha humana é fraca, então precisa de hash lento.

**Sessão no servidor.** O cookie guarda um valor aleatório; no banco fica só o hash dele, com data de expiração. Vantagem sobre cookie assinado: o logout realmente invalida (apaga a linha), e trocar a senha derruba todas as sessões da pessoa.

**Atributos do cookie.** `HttpOnly`: o JavaScript da página não lê (um XSS não rouba a sessão). `Secure`: só trafega por HTTPS. `SameSite=Lax`: o navegador não o envia em POST disparado por outro site. Em teste local por `http`, `PAINEL_COOKIE_SECURE=0`.

**CSRF.** Como o navegador anexa o cookie sozinho, um site malicioso poderia tentar fazer sua sessão executar uma ação. Defesa em duas camadas: `SameSite` e o header `X-TechDrop: 1` exigido em todo POST autenticado por cookie (outro site não consegue enviá-lo sem permissão CORS, que não damos). Mesmo padrão do painel local.

**Não revelar quem existe.** "Usuário não existe" e "senha errada" dão a mesma resposta, e para usuário inexistente rodamos um bcrypt falso para o tempo de resposta também ser igual.

**Limite de tentativas.** 5 senhas erradas bloqueiam aquele nome por 10 minutos, em memória. Tem um custo (um atacante poderia incomodar um admin conhecido), aceito no MVP porque são poucos usuários.

**Token aparece uma vez.** A resposta que cria o token é a única com o texto puro, marcada `Cache-Control: no-store`. Revogar filtra por `usuario_id`, então ninguém revoga token de outra pessoa.

**Redirect vs 401.** Páginas (`/`, `/tokens`) redirecionam para `/login` quando não há sessão. Rotas `/api` respondem 401, porque quem as chama é código, não uma pessoa.

## Achado na validação

O `getpass` do Windows lê direto do teclado e ignora entrada por pipe. Isso é correto para uma senha (não deve vir de arquivo ou histórico), mas significa que `criar-admin` só funciona interativamente. Na validação real criei o admin de teste por código, e o login, a geração de token, o envio das 42 ofertas reais, a revogação e o logout foram feitos no navegador.

## MVP, melhoria futura, desnecessário

- MVP: o que foi feito.
- Melhoria futura: limite de tentativas por IP e persistente, 2FA, expiração por inatividade, tela de admin para criar usuários, rate limit no Caddy.
- Desnecessário agora: OAuth, perfis de permissão, recuperação de senha por e-mail.
