# Etapa 6: guia por PC

Resumo de conceitos para levar ao Obsidian.

## O que foi feito

- `docs/compartilhamento-de-dados.md`: seções 3 (guia para rodar no PC), 4 (regras de uso), 7 (perguntas frequentes), mais linhas novas em "Solução de problemas" e no glossário.
- `requirements.txt`: adicionado `playwright-stealth`, que o `scraperd.py` importa e que não estava listado.

## Conceitos

**Documentação que alguém consegue seguir sozinho.** Um bom guia assume que o leitor não conhece o código: diz o que cada passo faz em uma frase, traz o comando pronto e diz como saber que deu certo. A estrutura segue a ordem real de uso (pré-requisitos, instalação, configuração, dia a dia, atualização).

**Teste num ambiente limpo.** O guia só vale se funcionar numa máquina sem nada instalado. Simulei um "PC B": copiei o `HEAD` do git para uma pasta nova, criei um venv novo, instalei só o `requirements.txt` e segui os passos. Foi assim que apareceu a falha que nenhum teste automático pegaria.

**Dependência declarada vs dependência usada.** O `scraperd.py` importa `playwright_stealth`, mas o `requirements.txt` não listava o pacote. No PC do desenvolvedor funcionava porque ele já estava instalado (e constava no `requirements-lock.txt`). Num PC novo quebraria na primeira execução. Regra: tudo que o código importa tem que estar no arquivo de requisitos, e a única forma de ter certeza é instalar do zero.

**Evitar a ativação do venv.** O guia chama `.venv\Scripts\python.exe` direto, em vez de `activate`. No Windows, ativar scripts costuma esbarrar na política de execução do PowerShell, um erro que confunde iniciantes. Chamar o executável pelo caminho evita o problema.

**Um token por pessoa e por PC.** Assim dá para revogar um PC perdido sem afetar os outros, e o campo "Enviado por" é confiável.

**Idempotência e descartes em dois níveis.** O descarte local é só do PC; o descarte online é compartilhado. O guia explica a diferença porque é a dúvida mais provável de quem usa os dois painéis.

**Regras de uso como proteção, não burocracia.** Poucas páginas, intervalo entre buscas, parar ao ver bloqueio, não compartilhar token nem perfil do navegador. Os números (3 páginas, 10 minutos) são uma recomendação conservadora do projeto, não um limite oficial da loja, e o texto diz isso.

## Validado aqui

Simulação de um segundo PC, do zero: venv novo, imports dos scrapers e do servidor, `.env` copiado do exemplo com as linhas descomentadas, painel local em modo de teste, coleta de teste pela API (6 ofertas), envio recusado para ofertas de teste, depois 42 ofertas no formato real enviadas a um painel online temporário (42 ofertas, 42 linhas de preço, `enviado_por` vindo do token).

**Não validado:** o download do Chromium e uma coleta real no Mercado Livre num PC novo.

## MVP, melhoria futura, desnecessário

- MVP: o que foi feito.
- Melhoria futura: instalador de um clique (script que faz clone, venv, Playwright e `.env`), guia em vídeo curto, suporte documentado a Mac e Linux, uma tela de "primeiros passos" no painel local.
- Desnecessário agora: empacotar em executável, Docker nos PCs.
