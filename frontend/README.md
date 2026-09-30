# TechDrop (frontend)

Painel web dark mode para o Grupo de Ofertas, focado no Mercado Livre. Tem duas
abas funcionando:

- **Produtos**: revisar, filtrar e marcar ofertas como enviadas.
- **Scraper**: rodar o `scraperd.py` pelo navegador, com o mesmo fluxo do terminal.

O frontend é HTML, CSS e JavaScript puros, sem build e sem Node. O Tailwind vem de
CDN (precisa de internet).

## Como rodar

Na raiz do projeto (PowerShell, uma linha):

```powershell
.\.venv\Scripts\python.exe techdrop_server.py
```

Abra `http://localhost:5500`. Alternativa: dois cliques em `frontend\iniciar.bat`.

O `techdrop_server.py` (na raiz do projeto) faz duas coisas: serve esta pasta e
executa o scraper. Sem ele a aba Produtos ainda abre (por exemplo com
`python -m http.server`), mas a aba Scraper mostra um aviso, porque o navegador não
consegue rodar o Playwright sozinho.

## Aba Scraper

Funciona como rodar `python scraperd.py` no terminal, só que pelo painel:

1. Preencha produto, desconto mínimo, páginas e (opcional) debug.
2. Clique em **Iniciar busca**. O painel responde as 4 perguntas do scraper por você
   e mostra tudo o que ele imprime, ao vivo, no terminal da página.
3. O Chrome abre na sua tela durante a busca. Não feche a janela.
4. Ao terminar, as ofertas entram na aba **Produtos** (somando à lista, sem
   duplicar por link). Marque "Substituir lista de Produtos" para começar do zero.

Outros controles:

- **Modo terminal**: inicia o scraper sem preencher nada e você digita cada resposta
  na linha `>` do terminal, igual ao terminal de verdade.
- **Parar**: interrompe a busca e fecha o Chrome aberto por ela.
- **Limpar**: limpa só a tela do terminal.

Se você recarregar a página no meio de uma busca, o terminal reconecta e continua de
onde estava.

### Como funciona por dentro

```
Navegador (aba Scraper)  ->  techdrop_server.py  ->  python scraperd.py
   formulário e terminal      FastAPI local            (processo separado)
```

O servidor abre o `scraperd.py` como um processo separado, digita as respostas no
`stdin` dele e repassa o `stdout` para a página. O scraper não é importado nem
alterado, então o comportamento é o mesmo do terminal. Ele só ganhou um pequeno
trecho no `main()` que, quando a variável `TECHDROP_OUTPUT` existe, salva os
resultados em JSON. No terminal normal esse trecho não faz nada.

O servidor escuta só em `127.0.0.1` (apenas o seu computador) e só aceita comandos
vindos do próprio painel.

## Aba Produtos

- Contadores e abas: Todos, Pendentes, Enviados
- Filtro por desconto mínimo, busca por título e ordenação
- "Marcar todos" (apenas o que está visível com os filtros atuais)
- Ações em lote: marcar selecionados como enviados
- **Preview & Enviar**: mostra a mensagem, permite copiar o texto e marcar como
  enviado (por enquanto só localmente, sem Telegram)
- "Desfazer" para voltar um item enviado a pendente

### Descartados

Cada card tem um botão de lixeira (e há "Descartar" na barra de lote). O produto sai
da lista e vai para a aba **Descartados**, onde fica **7 dias**. Depois disso é apagado
de vez.

- **Restaurar**: devolve o produto para a lista de Produtos (um ou vários selecionados).
- Em cada card aparece quanto tempo falta para apagar.
- Uma busca nova do scraper **não traz de volta** produtos descartados que ainda estão
  nos 7 dias (o terminal avisa quantos foram ignorados). Depois de apagados, se o
  scraper achar o produto de novo, ele volta como oferta nova.
- Os dados ficam em `data/descartados.json` (no `.gitignore`). O servidor confere e
  apaga os vencidos ao ligar, a cada hora, e sempre que a lista é aberta.
- Prazo configurável com a variável `TECHDROP_DIAS_DESCARTE` (padrão 7).
- Precisa do servidor rodando (`techdrop_server.py`), porque é ele quem guarda e apaga.

O status "Enviado" fica no `localStorage` do navegador (chave `ofertas_enviadas_v1`),
por link. É por navegador e por endereço (`localhost:5500`).

## Formato do JSON de ofertas

Lista de objetos (ou `{"items": [...]}`):

```json
{
  "title": "Notebook Acer Aspire 5",
  "price": 2799.90,
  "old_price": 3499.90,
  "discount": 20.0,
  "installment": "em 10x R$ 279,99 sem juros",
  "link": "https://www.mercadolivre.com.br/...",
  "image": "https://http2.mlstatic.com/....jpg"
}
```

`title` e `link` são obrigatórios. `link` também identifica o item (é a chave do
status "Enviado"). `image` é opcional: sem ele, o card mostra um ícone cinza.

## Estrutura

```
grupo-de-ofertas/
├── techdrop_server.py          # servidor local (serve o frontend + roda o scraper)
├── scraperd.py                 # scraper (roda como processo separado)
└── frontend/
    ├── index.html              # estrutura das abas
    ├── assets/
    │   ├── style.css           # estilos extras
    │   ├── app.js              # navegação, aba Produtos (estado, filtros, cards)
    │   └── scraper.js          # aba Scraper (terminal, formulário, consulta ao servidor)
    ├── data/
    │   ├── ofertas.sample.json # exemplo (versionado)
    │   └── ofertas.json        # gerado pelo scraper (no .gitignore)
    ├── iniciar.bat             # atalho para subir tudo
    └── README.md
```

## Para editar

- Arquivo do scraper usado: constante `SCRAPER` no `techdrop_server.py` (ou a
  variável de ambiente `TECHDROP_SCRAPER`)
- Porta: variável `TECHDROP_PORT` (padrão 5500)
- Mensagem do preview: função `mensagem(o)` em `assets/app.js`
- Aparência dos cards: função `card(o)` em `assets/app.js`

## Próximos passos (fora do MVP atual)

- Campo `image` no scraper para mostrar a foto real
- Trocar "marcar como enviado" por uma chamada que publica no Telegram
- Guardar o status "Enviado" no banco em vez do navegador
- Histórico das buscas feitas
