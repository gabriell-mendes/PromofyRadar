"""TechDrop: servidor local do painel.

Faz duas coisas:
1. Serve o frontend (pasta `frontend/`) em http://localhost:5500
2. Executa o scraper (`scraperd.py`) como se fosse no terminal: abre o processo,
   responde as perguntas (produto, desconto, páginas, debug), transmite a saída
   ao vivo para a aba "Scraper" e salva as ofertas em `frontend/data/ofertas.json`.
3. Envia as ofertas aprovadas ao painel online compartilhado (botão "Enviar ao painel"),
   usando PAINEL_URL e PAINEL_TOKEN do `.env`. O token fica só aqui no servidor local,
   nunca vai para o navegador.

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
from urllib.parse import urlparse

import requests
import uvicorn
from dotenv import dotenv_values
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from categorias_ml import CATEGORIAS, CUSTOM, TECNOLOGIA_SUB, categoria_painel, montar_url
from ofertas_abas import ABA_CATEGORIA, ABAS, CUSTOM as CUSTOM_ABA, validar_escolha as validar_aba
import telegram_envio

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = FRONTEND_DIR / "data"
OFERTAS_JSON = DATA_DIR / "ofertas.json"
DESCARTADOS_JSON = DATA_DIR / "descartados.json"
SAIDA_TEMP = DATA_DIR / "_ultima_busca.json"  # o scraper grava aqui (ver TECHDROP_OUTPUT)
DIAS_DESCARTE = int(os.environ.get("TECHDROP_DIAS_DESCARTE", "7"))  # descartados somem depois disso
SCRAPER = BASE_DIR / os.environ.get("TECHDROP_SCRAPER", "scraperd.py")  # scraper por busca
SCRAPER_CATEGORIA = BASE_DIR / os.environ.get("TECHDROP_SCRAPER_CATEGORIA", "scraper_categoria.py")
SCRAPER_OFERTAS = BASE_DIR / os.environ.get("TECHDROP_SCRAPER_OFERTAS", "scraper_ofertas.py")  # abas de Ofertas
PORTA = int(os.environ.get("TECHDROP_PORT", "5500"))
ENV_FILE = BASE_DIR / ".env"
LOTE_PAINEL = 200  # ofertas por pedido ao painel online (o limite dele é 500 ofertas e 1 MB)
TIMEOUT_PAINEL = 30  # segundos

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


def _ordenar(ofertas) -> list:
    """Melhor Deal Score primeiro, sem nota por último, desempate pelo desconto."""
    return sorted(
        ofertas,
        key=lambda o: (o.get("deal_score") is not None, o.get("deal_score") or 0, o.get("discount", 0)),
        reverse=True,
    )


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

    def __init__(self, respostas: list[str], substituir: bool, tipo: str = "busca", categoria: str | None = None,
                 min_score: int = 0):
        self.min_score = min_score  # só entram no painel ofertas com Deal Score >= isto (0 = todas)
        self.categoria = categoria  # categoria do painel, quando o scraper já sabe qual é
        self.tipo = tipo  # "busca" ou "categoria"
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
            ignoradas = len(coletadas) - len(novas)  # já descartadas (antes do filtro de nota)
            abaixo = 0
            if j.min_score > 0:  # filtro pela nota (sem nota fica de fora, não dá para provar que é boa)
                boas = [o for o in novas if o.get("deal_score") is not None and o["deal_score"] >= j.min_score]
                abaixo = len(novas) - len(boas)
                novas = boas
            if j.categoria:  # o scraper sabe a categoria; o resto o painel adivinha pelo título
                for o in novas:
                    o["category"] = j.categoria
            atuais = [] if j.substituir else _ler(OFERTAS_JSON)
            por_link = {o["link"]: o for o in atuais if o.get("link")}
            for o in novas:
                por_link[o["link"]] = o  # a coleta mais recente vence
            total = _ordenar(por_link.values())
            _gravar(OFERTAS_JSON, total)
        otimas = sum(1 for o in novas if (o.get("deal_score") or 0) >= 75)
        j.salvo = {"novas": len(novas), "total": len(total), "ignoradas": ignoradas,
                   "abaixo_da_nota": abaixo, "otimas": otimas, "min_score": j.min_score}
        extra = f" ({ignoradas} ignoradas por já estarem descartadas)" if ignoradas else ""
        corte = f" ({abaixo} abaixo do Deal Score mínimo {j.min_score})" if abaixo else ""
        j.emitir(f"\n[TechDrop] {len(novas)} ofertas desta busca{extra}{corte} | {len(total)} na lista de Produtos\n")
    except Exception as e:  # noqa: BLE001
        j.emitir(f"\n[TechDrop] Não consegui salvar as ofertas: {e}\n")


class StartBody(BaseModel):
    tipo: str = "busca"  # "busca" (scraperd.py), "categoria" ou "ofertas"
    aba: str = ""  # só no tipo "ofertas"
    aba_url: str = ""  # só quando aba == "Colar URL"
    categoria: str = ""  # só no tipo "categoria"
    subcategoria: str = ""
    url: str = ""  # só quando categoria == "Colar URL"
    query: str = ""
    min_discount: str = ""
    min_score: str = ""  # Deal Score mínimo (0 a 100) para entrar na lista de Produtos
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
        total = _ordenar(por_link.values())
        _gravar(OFERTAS_JSON, total)
    return {"restaurados": len(voltam)}


@app.post("/api/descartados/excluir", dependencies=[Depends(somente_painel)])
def excluir_descartados(body: LinksBody):
    """Apaga de vez (sem volta) os descartados escolhidos, sem esperar os 7 dias."""
    with DATA_LOCK:
        descartados = _purgar_descartados()
        alvo = set(body.links)
        restantes = [o for o in descartados if o.get("link") not in alvo]
        _gravar(DESCARTADOS_JSON, restantes)
    return {"excluidos": len(descartados) - len(restantes)}


# ---------- Envio ao painel online compartilhado ----------
class EnviarBody(BaseModel):
    links: list[str] | None = None  # None = todas as que ainda não foram enviadas


def _config_painel() -> tuple[str, str]:
    """(PAINEL_URL, PAINEL_TOKEN). Lê do ambiente e do `.env`, sem copiar o token para
    os.environ (senão ele iria junto para o processo do scraper)."""
    arquivo = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    url = (os.environ.get("PAINEL_URL") or arquivo.get("PAINEL_URL") or "").strip().rstrip("/")
    token = (os.environ.get("PAINEL_TOKEN") or arquivo.get("PAINEL_TOKEN") or "").strip()
    return url, token


def _validar_url_painel(url: str) -> str | None:
    """Mensagem de erro, ou None se a URL serve. O token vai em todo envio: por http puro
    ele passaria aberto pela rede, então só aceitamos http em localhost."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return "PAINEL_URL inválida. Use algo como https://painel.seudominio.com"
    if p.scheme == "http" and p.hostname not in ("localhost", "127.0.0.1", "::1"):
        return "PAINEL_URL precisa começar com https:// (o token não pode trafegar sem criptografia)."
    return None


def _para_painel(o: dict, coletado_em: str) -> dict:
    """Formato do scraper local -> contrato OfertaIn do painel online (painel_online/schemas.py)."""
    return {
        "loja": "mercadolivre",
        "url": o.get("link"),
        "titulo": o.get("title"),
        "preco": o.get("price"),
        "preco_original": o.get("old_price") or None,
        "desconto": o.get("discount"),
        "parcelamento": o.get("installment"),
        "imagem": o.get("image"),
        "categoria": o.get("category"),
        "deal_score": o.get("deal_score"),
        "deal_confianca": o.get("deal_confianca"),
        "deal_motivos": o.get("deal_motivos") or [],
        "deal_flags": o.get("deal_flags") or [],
        "coletado_em": coletado_em,
    }


def _erro_painel(status: int) -> tuple[int, str]:
    """(status HTTP que devolvemos ao painel local, mensagem clara)."""
    if status == 401:
        return 401, ("O painel recusou o token (inválido ou revogado). No painel online, vá em Meus tokens, "
                     "gere um novo e atualize PAINEL_TOKEN no .env.")
    if status in (301, 302, 303, 307, 308):
        return 502, "O painel redirecionou o envio. Confira se PAINEL_URL é o endereço final, com https://."
    if status in (413, 422):
        return 502, f"O painel recusou o formato ou o tamanho do envio (HTTP {status})."
    if status >= 500:
        return 502, f"O painel online está com problema (HTTP {status}). Tente de novo em alguns minutos."
    return 502, f"O painel recusou o envio (HTTP {status})."


def _marcar_enviadas(links: list[str]):
    """Anota em ofertas.json quais já foram ao painel (tira o aviso de pendente de envio).
    Uma nova coleta do mesmo produto sobrescreve a oferta e zera a marca: aí vale reenviar."""
    if not links:
        return
    agora = _agora().isoformat(timespec="seconds")
    alvo = set(links)
    with DATA_LOCK:
        atuais = _ler(OFERTAS_JSON)
        for o in atuais:
            if o.get("link") in alvo:
                o["enviado_painel_em"] = agora
        _gravar(OFERTAS_JSON, atuais)


@app.get("/api/painel/status")
def painel_status():
    """Diz se o envio está configurado e para onde vai. Nunca devolve o token."""
    url, token = _config_painel()
    return {"configurado": bool(url and token), "url": url or None}


def _config_afiliado() -> tuple[str, str]:
    """(matt_word, matt_tool) do link de afiliado do Mercado Livre. Não são segredo:
    aparecem em qualquer link que o afiliado compartilhe, então podem ir ao navegador."""
    arquivo = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    matt_word = (os.environ.get("AFILIADO_ML_MATT_WORD") or arquivo.get("AFILIADO_ML_MATT_WORD") or "").strip()
    matt_tool = (os.environ.get("AFILIADO_ML_MATT_TOOL") or arquivo.get("AFILIADO_ML_MATT_TOOL") or "").strip()
    return matt_word, matt_tool


@app.get("/api/afiliado/status")
def afiliado_status():
    """Diz se o link de afiliado está configurado e com quais valores."""
    matt_word, matt_tool = _config_afiliado()
    return {"configurado": bool(matt_word and matt_tool), "matt_word": matt_word or None, "matt_tool": matt_tool or None}


@app.post("/api/painel/enviar", dependencies=[Depends(somente_painel)])
def enviar_ao_painel(body: EnviarBody):
    """Manda ofertas ao painel online. Com `links`, só essas; sem, todas as ainda não enviadas.
    Reenviar é seguro: o painel não duplica (atualiza e soma uma linha no histórico de preços)."""
    url, token = _config_painel()
    if not url or not token:
        raise HTTPException(status_code=400, detail="Envio não configurado. Preencha PAINEL_URL e PAINEL_TOKEN no .env e reinicie o painel.")
    erro_url = _validar_url_painel(url)
    if erro_url:
        raise HTTPException(status_code=400, detail=erro_url)

    with DATA_LOCK:
        atuais = _ler(OFERTAS_JSON)
    if body.links is None:
        candidatas = [o for o in atuais if o.get("link") and not o.get("enviado_painel_em")]
    else:
        pedidos = set(body.links)
        candidatas = [o for o in atuais if o.get("link") in pedidos]

    # Ofertas de teste (iniciar_teste.bat) nunca vão para o painel de verdade.
    ofertas = [o for o in candidatas if not o.get("teste")]
    de_teste = len(candidatas) - len(ofertas)
    if not ofertas:
        aviso = " (ofertas de teste não são enviadas)" if de_teste else ""
        raise HTTPException(status_code=400, detail="Nenhuma oferta para enviar." + aviso)

    coletado_em = _agora().isoformat(timespec="seconds")
    total = {"criadas": 0, "atualizadas": 0, "ignoradas": 0, "detalhes_ignoradas": [], "de_teste": de_teste}
    enviadas_ok: list[str] = []

    for ini in range(0, len(ofertas), LOTE_PAINEL):
        lote = ofertas[ini:ini + LOTE_PAINEL]
        status_erro, falha = 502, None
        r = None
        try:
            r = requests.post(
                f"{url}/api/ingest",
                json={"ofertas": [_para_painel(o, coletado_em) for o in lote]},
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT_PAINEL,
                allow_redirects=False,  # nunca reenviar o token para outro endereço
            )
            if r.status_code != 200:
                status_erro, falha = _erro_painel(r.status_code)
        except requests.exceptions.SSLError:
            falha = "Falha de certificado HTTPS ao falar com o painel. Confira o PAINEL_URL."
        except requests.exceptions.Timeout:
            falha = f"O painel não respondeu em {TIMEOUT_PAINEL}s. Tente de novo."
        except requests.exceptions.ConnectionError:
            falha = f"Não consegui conectar em {url}. Confira sua internet e o PAINEL_URL."
        except requests.exceptions.RequestException as e:
            falha = f"Erro ao enviar ao painel: {type(e).__name__}."
        if falha:
            _marcar_enviadas(enviadas_ok)
            if enviadas_ok:
                falha += f" Já chegaram {len(enviadas_ok)} oferta(s) antes do erro; pode reenviar sem duplicar."
            raise HTTPException(status_code=status_erro, detail=falha)

        res = r.json()
        total["criadas"] += res["criadas"]
        total["atualizadas"] += res["atualizadas"]
        total["ignoradas"] += res["ignoradas"]
        recusadas = {d["indice"] for d in res["detalhes_ignoradas"]}
        for d in res["detalhes_ignoradas"]:
            alvo = lote[d["indice"]] if d["indice"] < len(lote) else {}
            total["detalhes_ignoradas"].append({"titulo": (alvo.get("title") or "")[:80], "motivo": d["motivo"]})
        enviadas_ok += [o["link"] for i, o in enumerate(lote) if i not in recusadas]

    _marcar_enviadas(enviadas_ok)
    return total


# ---------- Envio ao Telegram ----------
TELEGRAM_MAX = 4096  # limite do Telegram por mensagem


class TelegramBody(BaseModel):
    texto: str


@app.get("/api/telegram/status")
def telegram_status():
    """Diz se o Telegram está configurado. Nunca devolve token nem chat id."""
    token, chat = telegram_envio._config()
    return {"configurado": bool(token and chat)}


@app.post("/api/telegram/enviar", dependencies=[Depends(somente_painel)])
def enviar_ao_telegram(body: TelegramBody):
    """Manda ao Telegram o texto que você revisou (e talvez editou) no preview.
    O envio é sempre manual: um clique, uma mensagem."""
    texto = body.texto.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")
    if len(texto) > TELEGRAM_MAX:
        raise HTTPException(status_code=400, detail=f"Mensagem grande demais ({len(texto)} de {TELEGRAM_MAX} caracteres).")
    ok, erro = telegram_envio.enviar_mensagem(texto)
    if not ok:
        raise HTTPException(status_code=400 if "configurado" in erro else 502, detail=erro)
    return {"ok": True}


@app.get("/api/ping")
def ping():
    return {
        "ok": True,
        "scraper": SCRAPER.name,
        "scraper_existe": SCRAPER.exists(),
        "categoria_scraper": SCRAPER_CATEGORIA.name,
        "categoria_existe": SCRAPER_CATEGORIA.exists(),
        "ofertas_scraper": SCRAPER_OFERTAS.name,
        "ofertas_existe": SCRAPER_OFERTAS.exists(),
    }


@app.get("/api/abas")
def abas():
    """Abas da página de Ofertas para os botões da tela (fonte única: ofertas_abas.py)."""
    return {"abas": ABAS, "custom": CUSTOM_ABA}


@app.get("/api/categorias")
def categorias():
    """Categorias para os botões da tela do scraper (fonte única: categorias_ml.py)."""
    return {
        "categorias": [
            {"nome": nome, "subs": list(TECNOLOGIA_SUB) if slug is None else None}
            for nome, slug in CATEGORIAS.items()
        ],
        "custom": CUSTOM,
    }


@app.post("/api/scraper/start", dependencies=[Depends(somente_painel)])
def start(body: StartBody):
    global job
    if job and job.rodando:
        raise HTTPException(status_code=409, detail="Já existe uma busca rodando")
    if body.tipo not in ("busca", "categoria", "ofertas"):
        raise HTTPException(status_code=400, detail="Tipo de scraper inválido")
    script = {"busca": SCRAPER, "categoria": SCRAPER_CATEGORIA, "ofertas": SCRAPER_OFERTAS}[body.tipo]
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"Scraper não encontrado: {script.name}")

    try:
        min_score = int(body.min_score.strip() or 0)
    except ValueError:
        raise HTTPException(status_code=400, detail="Deal Score mínimo deve ser um número de 0 a 100")
    if not 0 <= min_score <= 100:
        raise HTTPException(status_code=400, detail="Deal Score mínimo deve ser um número de 0 a 100")

    env_extra = {}
    if body.tipo == "busca":
        if not body.manual and not body.query.strip():
            raise HTTPException(status_code=400, detail="Informe o produto")
    elif body.tipo == "ofertas":
        if not body.manual:
            try:
                validar_aba(body.aba, body.aba_url)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            env_extra = {"TECHDROP_ABA": body.aba, "TECHDROP_ABA_URL": body.aba_url}
    elif not body.manual:
        # Valida a escolha aqui (erro claro no painel) e passa ao scraper por variáveis
        # de ambiente, assim ele pula o menu numerado do terminal.
        try:
            montar_url(body.categoria, body.subcategoria, body.url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        env_extra = {
            "TECHDROP_CATEGORIA": body.categoria,
            "TECHDROP_SUBCATEGORIA": body.subcategoria,
            "TECHDROP_CATEGORIA_URL": body.url,
        }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SAIDA_TEMP.unlink(missing_ok=True)

    # Mesma ordem das perguntas do scraper no terminal
    # busca:     produto, desconto, páginas, debug
    # categoria: desconto, páginas, debug (a categoria já foi escolhida acima)
    respostas = [body.min_discount.strip(), body.max_pages.strip(), "s" if body.debug else ""]
    if body.tipo == "busca":
        respostas.insert(0, body.query.strip())
    if body.manual:
        respostas = []
    categoria_job = None
    if not body.manual:
        if body.tipo == "categoria" and body.categoria in CATEGORIAS:
            categoria_job = categoria_painel(body.categoria, body.subcategoria)
        elif body.tipo == "ofertas":
            categoria_job = ABA_CATEGORIA.get(body.aba)
    j = Job(respostas, body.substituir, body.tipo, categoria_job, min_score)
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8",
           "TECHDROP_OUTPUT": str(SAIDA_TEMP), **env_extra}
    j.proc = subprocess.Popen(
        [sys.executable, "-u", str(script)],
        cwd=str(BASE_DIR),  # igual a rodar o scraper da raiz do projeto (browser_profile etc.)
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    j.emitir(f"$ python {script.name}\n")
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
        "tipo": job.tipo,
        "id": int(job.inicio),
    }


# Frontend estático por último, para não cobrir as rotas /api
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    threading.Thread(target=_purga_periodica, daemon=True).start()
    print(f"TechDrop rodando em http://localhost:{PORTA}  (Ctrl+C para parar)")
    uvicorn.run(app, host="127.0.0.1", port=PORTA, log_level="warning")
