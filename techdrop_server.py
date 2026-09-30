"""TechDrop: servidor local do painel.

Faz duas coisas:
1. Serve o frontend (pasta `frontend/`) em http://localhost:5500
2. Executa o scraper (`scraperd.py`) como se fosse no terminal: abre o processo,
   responde as perguntas (produto, desconto, páginas, debug), transmite a saída
   ao vivo para a aba "Scraper" e salva as ofertas em `frontend/data/ofertas.json`.

O scraper NÃO é importado: ele roda como um processo separado, exatamente como
`python scraperd.py` no terminal. Assim o painel nunca muda o comportamento dele.

Rodar (na raiz do projeto):  python techdrop_server.py
"""

import codecs
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = FRONTEND_DIR / "data"
OFERTAS_JSON = DATA_DIR / "ofertas.json"
DESCARTADOS_JSON = DATA_DIR / "descartados.json"
SAIDA_TEMP = DATA_DIR / "_ultima_busca.json"  # o scraper grava aqui (ver TECHDROP_OUTPUT)
DIAS_DESCARTE = int(os.environ.get("TECHDROP_DIAS_DESCARTE", "7"))  # descartados somem depois disso
SCRAPER = BASE_DIR / os.environ.get("TECHDROP_SCRAPER", "scraperd.py")
PORTA = int(os.environ.get("TECHDROP_PORT", "5500"))

app = FastAPI(title="TechDrop")


# Proteção simples: só aceita POST vindo do nosso próprio painel. Outro site aberto
# no navegador não consegue mandar esse header sem permissão (não habilitamos CORS).
def somente_painel(x_techdrop: str = Header(default="")):
    if x_techdrop != "1":
        raise HTTPException(status_code=403, detail="Requisição não permitida")


# ---------- Arquivos de dados (ofertas e descartados) ----------
DATA_LOCK = threading.RLock()  # evita duas gravações ao mesmo tempo (scraper + painel)


def _ler(caminho: Path) -> list:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(caminho: Path, dados: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(caminho)  # troca atômica: nunca fica um arquivo pela metade


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _purgar_descartados() -> list:
    """Apaga de vez os descartados com mais de DIAS_DESCARTE dias e devolve os que ficaram."""
    with DATA_LOCK:
        itens = _ler(DESCARTADOS_JSON)
        limite = _agora() - timedelta(days=DIAS_DESCARTE)
        ficam = []
        for o in itens:
            try:
                quando = datetime.fromisoformat(o["discarded_at"])
                if quando.tzinfo is None:
                    quando = quando.replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                quando = _agora()  # data ilegível: começa a contar de agora
                o["discarded_at"] = quando.isoformat()
            if quando > limite:
                ficam.append(o)
        if len(ficam) != len(itens):
            _gravar(DESCARTADOS_JSON, ficam)
        return ficam


def _purga_periodica():
    while True:
        _purgar_descartados()
        time.sleep(3600)  # confere de hora em hora enquanto o servidor estiver ligado


class Job:
    """Estado da execução atual do scraper (só existe uma por vez)."""

    def __init__(self, respostas: list[str], substituir: bool):
        self.respostas = respostas  # respostas automáticas, na ordem dos prompts
        self.substituir = substituir
        self.saida = ""  # tudo que o scraper imprimiu (stdout + stderr)
        self.rodando = True
        self.codigo = None
        self.salvo = None  # {"novas": n, "total": m} depois de terminar
        self.proc = None
        self.lock = threading.Lock()
        self.inicio = time.time()

    def emitir(self, texto: str):
        with self.lock:
            self.saida += texto


job: Job | None = None


def _ler_saida(j: Job):
    """Thread: lê a saída do processo em tempo real e responde os prompts."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    pipe = j.proc.stdout
    while True:
        dados = pipe.read1(4096)
        if not dados:
            break
        texto = decoder.decode(dados)
        j.emitir(texto)
        # O scraper faz input("... : "). Quando a saída termina num prompt e ainda
        # temos uma resposta automática na fila, digitamos por você (com eco).
        if j.respostas and texto.endswith(": "):
            resposta = j.respostas.pop(0)
            _escrever_stdin(j, resposta)
            j.emitir(resposta + "\n")
    j.proc.wait()
    j.codigo = j.proc.returncode
    _salvar_resultados(j)
    j.rodando = False


def _escrever_stdin(j: Job, texto: str):
    try:
        j.proc.stdin.write((texto + "\n").encode("utf-8"))
        j.proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass


def _salvar_resultados(j: Job):
    """Depois que o scraper termina, junta as ofertas em data/ofertas.json."""
    if not SAIDA_TEMP.exists():
        return
    try:
        coletadas = json.loads(SAIDA_TEMP.read_text(encoding="utf-8"))
        SAIDA_TEMP.unlink()
        with DATA_LOCK:
            # Produtos descartados (ainda dentro dos 7 dias) não voltam para a lista
            descartados = {o.get("link") for o in _purgar_descartados()}
            novas = [o for o in coletadas if o.get("link") not in descartados]
            ignoradas = len(coletadas) - len(novas)
            atuais = [] if j.substituir else _ler(OFERTAS_JSON)
            por_link = {o["link"]: o for o in atuais if o.get("link")}
            for o in novas:
                por_link[o["link"]] = o  # a coleta mais recente vence
            total = sorted(por_link.values(), key=lambda o: o.get("discount", 0), reverse=True)
            _gravar(OFERTAS_JSON, total)
        j.salvo = {"novas": len(novas), "total": len(total), "ignoradas": ignoradas}
        extra = f" ({ignoradas} ignoradas por já estarem descartadas)" if ignoradas else ""
        j.emitir(f"\n[TechDrop] {len(novas)} ofertas desta busca{extra} | {len(total)} na lista de Produtos\n")
    except Exception as e:  # noqa: BLE001
        j.emitir(f"\n[TechDrop] Não consegui salvar as ofertas: {e}\n")


class StartBody(BaseModel):
    query: str = ""
    min_discount: str = ""
    max_pages: str = ""
    debug: bool = False
    substituir: bool = False
    manual: bool = False  # True: você responde os prompts digitando no terminal


class StdinBody(BaseModel):
    text: str = ""


class OffersBody(BaseModel):
    offers: list[dict] = []


class LinksBody(BaseModel):
    links: list[str] = []


@app.get("/api/descartados")
def listar_descartados():
    """Lista os descartados (já sem os que passaram de 7 dias)."""
    return {"items": _purgar_descartados(), "dias": DIAS_DESCARTE}


@app.post("/api/descartar", dependencies=[Depends(somente_painel)])
def descartar(body: OffersBody):
    """Tira as ofertas da lista de Produtos e guarda em descartados.json com a data."""
    with DATA_LOCK:
        descartados = _purgar_descartados()
        ja = {o.get("link") for o in descartados}
        agora = _agora().isoformat()
        for o in body.offers:
            link = o.get("link")
            if link and link not in ja:
                descartados.append({**o, "discarded_at": agora})
                ja.add(link)
        _gravar(DESCARTADOS_JSON, descartados)
        sair = {o.get("link") for o in body.offers}
        if OFERTAS_JSON.exists():
            atuais = _ler(OFERTAS_JSON)
            restantes = [o for o in atuais if o.get("link") not in sair]
            if len(restantes) != len(atuais):
                _gravar(OFERTAS_JSON, restantes)
    return {"descartados": len(descartados)}


@app.post("/api/restaurar", dependencies=[Depends(somente_painel)])
def restaurar(body: LinksBody):
    """Devolve ofertas descartadas para a lista de Produtos."""
    with DATA_LOCK:
        descartados = _purgar_descartados()
        alvo = set(body.links)
        voltam = [{k: v for k, v in o.items() if k != "discarded_at"}
                  for o in descartados if o.get("link") in alvo]
        _gravar(DESCARTADOS_JSON, [o for o in descartados if o.get("link") not in alvo])
        por_link = {o["link"]: o for o in _ler(OFERTAS_JSON) if o.get("link")}
        for o in voltam:
            por_link[o["link"]] = o
        total = sorted(por_link.values(), key=lambda o: o.get("discount", 0), reverse=True)
        _gravar(OFERTAS_JSON, total)
    return {"restaurados": len(voltam)}


@app.get("/api/ping")
def ping():
    return {"ok": True, "scraper": SCRAPER.name, "scraper_existe": SCRAPER.exists()}


@app.post("/api/scraper/start", dependencies=[Depends(somente_painel)])
def start(body: StartBody):
    global job
    if job and job.rodando:
        raise HTTPException(status_code=409, detail="Já existe uma busca rodando")
    if not SCRAPER.exists():
        raise HTTPException(status_code=500, detail=f"Scraper não encontrado: {SCRAPER.name}")
    if not body.manual and not body.query.strip():
        raise HTTPException(status_code=400, detail="Informe o produto")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SAIDA_TEMP.unlink(missing_ok=True)

    # Mesma ordem das perguntas do scraper no terminal
    respostas = [] if body.manual else [
        body.query.strip(),
        body.min_discount.strip(),
        body.max_pages.strip(),
        "s" if body.debug else "",
    ]
    j = Job(respostas, body.substituir)
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8",
           "TECHDROP_OUTPUT": str(SAIDA_TEMP)}
    j.proc = subprocess.Popen(
        [sys.executable, "-u", str(SCRAPER)],
        cwd=str(BASE_DIR),  # igual a rodar o scraper da raiz do projeto (browser_profile etc.)
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    j.emitir(f"$ python {SCRAPER.name}\n")
    job = j
    threading.Thread(target=_ler_saida, args=(j,), daemon=True).start()
    return {"ok": True}


@app.post("/api/scraper/stdin", dependencies=[Depends(somente_painel)])
def stdin(body: StdinBody):
    if not job or not job.rodando:
        raise HTTPException(status_code=409, detail="Nenhuma busca rodando")
    _escrever_stdin(job, body.text)
    job.emitir(body.text + "\n")  # eco, como no terminal
    return {"ok": True}


@app.post("/api/scraper/stop", dependencies=[Depends(somente_painel)])
def stop():
    if not job or not job.rodando:
        return {"ok": True}
    pid = job.proc.pid
    if os.name == "nt":
        # /T mata também o Chromium aberto pelo Playwright
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        job.proc.terminate()
    job.emitir("\n[TechDrop] Busca interrompida.\n")
    return {"ok": True}


@app.get("/api/scraper/output")
def output(since: int = 0):
    """O painel consulta isto a cada ~0,7 s; `since` é quanto texto ele já tem."""
    if not job:
        return {"text": "", "next": 0, "running": False, "started": False}
    with job.lock:
        texto = job.saida[since:]
        proximo = len(job.saida)
    return {
        "text": texto,
        "next": proximo,
        "running": job.rodando,
        "started": True,
        "exit_code": job.codigo,
        "saved": job.salvo,
        "id": int(job.inicio),
    }


# Frontend estático por último, para não cobrir as rotas /api
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    threading.Thread(target=_purga_periodica, daemon=True).start()
    print(f"TechDrop rodando em http://localhost:{PORTA}  (Ctrl+C para parar)")
    uvicorn.run(app, host="127.0.0.1", port=PORTA, log_level="warning")
