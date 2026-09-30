/* ============ ABA SCRAPER ============
 * Conversa com o servidor local (techdrop_server.py):
 *   POST /api/scraper/start   inicia o scraperd.py (como `python scraperd.py`)
 *   POST /api/scraper/stdin   envia uma linha digitada para o scraper
 *   POST /api/scraper/stop    interrompe
 *   GET  /api/scraper/output  saída ao vivo (consulta a cada 0,7 s)
 */
(() => {
  const term = $('sTerm');
  let since = 0;          // quanto texto do terminal já foi mostrado
  let lastId = null;      // identifica a execução atual no servidor
  let rodando = false;
  let paradoPorMim = false;
  let servidorOk = false;

  const post = async (url, body = {}) => {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-TechDrop': '1' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      let msg = `Erro ${r.status}`;
      try { msg = (await r.json()).detail || msg; } catch {}
      throw new Error(msg);
    }
    return r.json();
  };

  function aviso(texto) {
    $('sAviso').textContent = texto || '';
    $('sAviso').classList.toggle('hidden', !texto);
  }

  function escreve(texto) {
    if (!texto) return;
    const noFim = term.scrollHeight - term.scrollTop - term.clientHeight < 60;
    term.appendChild(document.createTextNode(texto));
    if (noFim) term.scrollTop = term.scrollHeight;
  }

  function status(rotulo, cor) {
    const el = $('sStatus');
    el.textContent = rotulo;
    el.className = `text-xs font-bold px-3 py-1.5 rounded-full ${cor}`;
  }

  function atualizaBotoes() {
    $('sStart').disabled = rodando || !servidorOk;
    $('sManual').disabled = rodando || !servidorOk;
    $('sStop').classList.toggle('hidden', !rodando);
    $('sInput').disabled = !rodando;
    for (const id of ['sQuery', 'sMin', 'sPages', 'sDebug', 'sReplace']) $(id).disabled = rodando;
    if (rodando) $('sInput').focus();
  }

  async function checaServidor() {
    try {
      const r = await fetch('/api/ping');
      const j = await r.json();
      servidorOk = !!j.ok;
      aviso(j.scraper_existe ? '' : `Não encontrei ${j.scraper} na raiz do projeto.`);
      if (!j.scraper_existe) servidorOk = false;
    } catch {
      servidorOk = false;
      aviso('Servidor do TechDrop não encontrado. Abra o painel pelo iniciar.bat (ou rode: python techdrop_server.py) e acesse http://localhost:5500');
    }
    atualizaBotoes();
  }

  async function consulta() {
    if (!servidorOk) return;
    let d;
    try {
      const r = await fetch(`/api/scraper/output?since=${since}`);
      d = await r.json();
    } catch { return; }

    if (!d.started) return;
    if (d.id !== lastId) {           // execução nova (ou página recarregada): recomeça do zero
      lastId = d.id; since = 0; term.textContent = '';
      const r = await fetch('/api/scraper/output?since=0');
      d = await r.json();
    }
    escreve(d.text);
    since = d.next;

    const eraRodando = rodando;
    rodando = d.running;
    if (rodando) {
      status('RODANDO', 'bg-emerald-500/20 text-emerald-300 animate-pulse');
    } else if (paradoPorMim) {
      status('ENCERRADO', 'bg-amber-500/20 text-amber-300');
    } else if (d.exit_code === 0) {
      status('FINALIZADO', 'bg-sky-500/20 text-sky-300');
    } else {
      status(`ERRO (código ${d.exit_code})`, 'bg-red-500/20 text-red-300');
    }
    atualizaBotoes();

    if (eraRodando && !rodando) {    // acabou de terminar
      paradoPorMim = false;
      if (d.saved) {
        $('sResumoTxt').textContent = `${d.saved.novas} ofertas desta busca. A lista de Produtos agora tem ${d.saved.total}.` + (d.saved.ignoradas ? ` (${d.saved.ignoradas} ignoradas por estarem descartadas)` : '');
        $('sResumo').classList.remove('hidden');
        carregar();                  // atualiza a aba Produtos (função do app.js)
      }
    }
  }

  async function iniciar(manual) {
    aviso('');
    const query = $('sQuery').value.trim();
    if (!manual && !query) { aviso('Informe o produto que deseja buscar.'); $('sQuery').focus(); return; }
    try {
      await post('/api/scraper/start', {
        query,
        min_discount: $('sMin').value,
        max_pages: $('sPages').value,
        debug: $('sDebug').checked,
        substituir: $('sReplace').checked,
        manual,
      });
      since = 0; lastId = null; term.textContent = ''; paradoPorMim = false;
      $('sResumo').classList.add('hidden');
      rodando = true;
      status('RODANDO', 'bg-emerald-500/20 text-emerald-300 animate-pulse');
      atualizaBotoes();
      consulta();
    } catch (e) {
      aviso(e.message);
    }
  }

  $('sForm').addEventListener('submit', (e) => { e.preventDefault(); iniciar(false); });
  $('sManual').addEventListener('click', () => iniciar(true));
  $('sStop').addEventListener('click', async () => {
    paradoPorMim = true;
    try { await post('/api/scraper/stop'); } catch (e) { aviso(e.message); }
  });
  $('sInputForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const texto = $('sInput').value;
    $('sInput').value = '';
    try { await post('/api/scraper/stdin', { text: texto }); } catch (err) { aviso(err.message); }
  });
  $('sClear').addEventListener('click', () => { term.textContent = ''; });
  $('sVerProdutos').addEventListener('click', () => setView('produtos'));

  document.addEventListener('viewchange', (e) => {
    if (e.detail === 'scraper') checaServidor().then(consulta);
  });

  // Consulta o servidor enquanto a aba está aberta ou enquanto há busca rodando
  setInterval(() => { if (viewAtual === 'scraper' || rodando) consulta(); }, 700);

  atualizaBotoes();
  if (viewAtual === 'scraper') checaServidor().then(consulta);
  else checaServidor();
})();
