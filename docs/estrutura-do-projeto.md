# Estrutura do projeto

Guia rápido para quem entra no repositório. Tudo que está listado aqui já existia, só foi reorganizado.

## Raiz

| Item | Para que serve |
|---|---|
| `techdrop_server.py` | Servidor FastAPI do painel TechDrop (serve o `frontend/` e dispara os scrapers) |
| `scraperd.py` | Scraper de busca por termo (Mercado Livre, Playwright) e classe base dos outros scrapers |
| `scraper_categoria.py` | Scraper por categoria |
| `scraper_ofertas.py` | Scraper da página de ofertas (abas) |
| `categorias_ml.py`, `ofertas_abas.py` | Listas de categorias e abas usadas pelos scrapers e pelo servidor |
| `deal_score.py`, `pontuacao.py`, `historico.py` | Deal Score, pontuação das ofertas e histórico de preços (SQLite) |
| `teste_base.py`, `scraper_teste_*.py` | Scrapers de teste, sem navegador, usados pelo `frontend/iniciar_teste.bat` |
| `rlscraper.py`, `scrapertest.py` | Versões experimentais anteriores dos scrapers |
| `requirements*.txt`, `.env.example` | Dependências e exemplo de variáveis de ambiente. `requirements-painel.txt` é só o que o servidor online precisa |

Os arquivos `.py` da raiz ficam juntos de propósito: eles se importam pelo nome (`from pontuacao import ...`) e os scrapers gravam `browser_profile/` e `debug_snapshots/` a partir da raiz. Mover qualquer um exige ajustar imports e caminhos.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `painel_online/` | Painel online compartilhado (FastAPI + SQLite): recebe, guarda e exibe as ofertas dos PCs. Roda no VPS |
| `deploy/` | Arquivos do servidor: serviço systemd, Caddyfile, cron de backup, script de atualização |
| `app/` | Primeira versão do projeto (dashboard de revisão, fontes, filtro, score, storage) |
| `frontend/` | Painel web (HTML, JS, CSS) e `.bat` para iniciar |
| `data/` | Bancos SQLite e dados locais |
| `docs/` | Documentação do projeto |
| `docs/historico-de-sessoes/` | Notas e versões antigas salvas de sessões com o Claude |
| `tests/` | Testes automatizados (pytest) |
| `browser_profile/` | Perfil do navegador usado pelos scrapers (local, fora do Git) |
| `debug_snapshots/` | HTMLs de debug gerados pelos scrapers (local, fora do Git) |

## `_arquivo/` (somente na sua máquina, fora do Git)

Material antigo que não é usado pelo código. Pode ser apagado quando quiser liberar espaço.

| Pasta | Conteúdo |
|---|---|
| `_arquivo/backups/` | Arquivos `.bak_antes_*` (cópias antes de cada mudança) |
| `_arquivo/debug/` | Screenshot e HTML de debug soltos |
| `_arquivo/perfis-navegador-antigos/` | Perfis de navegador de experimentos anteriores (`ml_session_*`, `lightning_offers_*`, `smart_offers_*`, `all_offers_profile`) |
