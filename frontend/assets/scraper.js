/* ============ ABA SCRAPER ============
 * Duas telas dentro da aba:
 *   1. Escolha do tipo de scraper (por busca de produto ou por categoria)
 *   2. Formulário + terminal do tipo escolhido
 *
 * Conversa com o servidor local (techdrop_server.py):
 *   GET  /api/categorias      lista de categorias (vem do categorias_ml.py)
 *   POST /api/scraper/start   inicia o scraper escolhido (campo "tipo")
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

  let tipo = null;        // 'busca' | 'categoria' | null (tela de escolha)
  let ping = {};          // última resposta de /api/ping
  let categorias = null;  // [{nome, subs}] carregado do servidor
  let custom = 'Colar URL';
  let catSel = '';        // nome da categoria escolhida
  let abas = null;        // nomes das abas da página de Ofertas
  let abaSel = '';        // aba escolhida

  const TIPOS = {
    busca: {
      rotulo: 'Por busca',
      script: 'python scraperd.py',
      descricao: 'Mesmo fluxo do terminal: produto, desconto mínimo, páginas e debug. O Chrome abre na sua tela durante a busca.',
    },
    categoria: {
      rotulo: 'Por categoria',
      script: 'python scraper_categoria.py',
      descricao: 'Escolha uma categoria, o desconto mínimo e as páginas. O Chrome abre na sua tela durante a busca.',
    },
    ofertas: {
      rotulo: 'Por aba de Ofertas',
      script: 'python scraper_ofertas.py',
      descricao: 'Escolha uma aba da página de Ofertas (Relâmpago, Outlet, Celulares...), o desconto mínimo e as páginas. O Chrome abre na sua tela durante a busca.',
    },
  };

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

  // ---------- Escolha do tipo ----------
  function scriptOk() {
    if (tipo === 'busca') return !!ping.scraper_existe;
    if (tipo === 'categoria') return !!ping.categoria_existe;
    if (tipo === 'ofertas') return !!ping.ofertas_existe;
    return true;
  }

  function avisaScript() {
    if (!servidorOk || !tipo) return;
    if (tipo === 'busca' && !ping.scraper_existe) aviso(`Não encontrei ${ping.scraper} na raiz do projeto.`);
    else if (tipo === 'categoria' && !ping.categoria_existe) aviso(`Não encontrei ${ping.categoria_scraper} na raiz do projeto.`);
    else if (tipo === 'ofertas' && !ping.ofertas_existe) aviso(`Não encontrei ${ping.ofertas_scraper} na raiz do projeto.`);
    else aviso('');
  }

  function mostrarEscolha() {
    if (rodando) return;
    tipo = null;
    aviso('');
    $('sEscolha').classList.remove('hidden');
    $('sTela').classList.add('hidden');
  }

  function mostrarTela(t) {
    tipo = t;
    const info = TIPOS[t];
    $('sEscolha').classList.add('hidden');
    $('sTela').classList.remove('hidden');
    $('sTipoRotulo').textContent = info.rotulo;
    $('sDescricao').textContent = info.descricao;
    $('sTermTitulo').textContent = info.script;
    $('sCamposBusca').classList.toggle('hidden', t !== 'busca');
    $('sCamposCategoria').classList.toggle('hidden', t !== 'categoria');
    if (!rodando) {
      term.textContent = '';
      $('sResumo').classList.add('hidden');
      status('PARADO', 'bg-slate-700 text-slate-300');
    }
    $('sCamposOfertas').classList.toggle('hidden', t !== 'ofertas');
    if (t === 'categoria') carregarCategorias();
    if (t === 'ofertas') carregarAbas();
    avisaScript();
    atualizaBotoes();
  }

  // ---------- Categorias ----------
  async function carregarCategorias() {
    if (categorias) { renderCategorias(); return; }
    try {
      const r = await fetch('/api/categorias');
      const j = await r.json();
      categorias = j.categorias;
      custom = j.custom || custom;
      renderCategorias();
    } catch {
      $('sCatGrid').textContent = 'Não consegui carregar as categorias.';
    }
  }

  function renderCategorias() {
    const grid = $('sCatGrid');
    grid.textContent = '';
    const nomes = [...categorias.map(c => c.nome), custom];
    for (const nome of nomes) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = nome === custom ? 'Colar URL...' : nome;
      b.dataset.nome = nome;
      b.className = 'px-3 py-1.5 text-xs rounded-full border disabled:opacity-40 disabled:cursor-not-allowed ' +
        (nome === catSel
          ? 'border-emerald-500 bg-emerald-500/15 text-emerald-300'
          : 'border-line bg-bg text-slate-300 hover:border-slate-500');
      b.addEventListener('click', () => escolheCategoria(nome));
      grid.appendChild(b);
    }
    atualizaCamposCategoria();
    atualizaBotoes();
  }

  function escolheCategoria(nome) {
    catSel = nome;
    renderCategorias();
  }

  function atualizaCamposCategoria() {
    const cat = categorias && categorias.find(c => c.nome === catSel);
    const temSub = !!(cat && cat.subs);
    $('sSubWrap').classList.toggle('hidden', !temSub);
    if (temSub) {
      const sel = $('sSub');
      sel.textContent = '';
      sel.appendChild(new Option('Escolha...', ''));
      for (const s of cat.subs) sel.appendChild(new Option(s, s));
    }
    $('sUrlWrap').classList.toggle('hidden', catSel !== custom);
    $('sCatSel').textContent = catSel
      ? (catSel === custom ? 'Cole a URL de uma categoria do Mercado Livre.' : `Categoria: ${catSel}`)
      : 'Nenhuma categoria escolhida.';
  }

  // ---------- Abas de Ofertas ----------
  async function carregarAbas() {
    if (abas) { renderAbas(); return; }
    try {
      const r = await fetch('/api/abas');
      const j = await r.json();
      abas = j.abas;
      custom = j.custom || custom;
      renderAbas();
    } catch {
      $('sAbaGrid').textContent = 'Não consegui carregar as abas.';
    }
  }

  function renderAbas() {
    const grid = $('sAbaGrid');
    grid.textContent = '';
    for (const nome of [...abas, custom]) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = nome === custom ? 'Colar URL...' : nome;
      b.className = 'px-3 py-1.5 text-xs rounded-full border disabled:opacity-40 disabled:cursor-not-allowed ' +
        (nome === abaSel
          ? 'border-emerald-500 bg-emerald-500/15 text-emerald-300'
          : 'border-line bg-bg text-slate-300 hover:border-slate-500');
      b.addEventListener('click', () => { abaSel = nome; renderAbas(); });
      grid.appendChild(b);
    }
    $('sAbaUrlWrap').classList.toggle('hidden', abaSel !== custom);
    $('sAbaSel').textContent = abaSel
      ? (abaSel === custom ? 'Cole a URL de uma aba da página de Ofertas.' : `Aba: ${abaSel}`)
      : 'Nenhuma aba escolhida.';
    atualizaBotoes();
  }

  // ---------- Estado dos botões ----------
  function atualizaBotoes() {
    $('sStart').disabled = rodando || !servidorOk || !scriptOk();
    $('sManual').disabled = rodando || !servidorOk || !scriptOk();
    $('sStop').classList.toggle('hidden', !rodando);
    $('sVoltar').disabled = rodando;
    $('sInput').disabled = !rodando;
    for (const id of ['sQuery', 'sMin', 'sMinScore', 'sPages', 'sDebug', 'sReplace', 'sSub', 'sUrl', 'sAbaUrl']) $(id).disabled = rodando;
    for (const g of ['sCatGrid', 'sAbaGrid']) $(g).querySelectorAll('button').forEach(b => { b.disabled = rodando; });
    if (rodando) $('sInput').focus();
  }

  async function checaServidor() {
    try {
      const r = await fetch('/api/ping');
      ping = await r.json();
      servidorOk = !!ping.ok;
      avisaScript();
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
    // Página recarregada com uma busca rodando: abre direto a tela do tipo certo
    if (tipo === null && d.running) mostrarTela(d.tipo || 'busca');
    if (d.id !== lastId) {           // execução nova (ou página recarregada): recomeça do zero
      lastId = d.id; since = 0; term.textContent = '';
      const r = await fetch('/api/scraper/output?since=0');
      d = await r.json();
    }
    escreve(d.text);
    since = d.next;

    const eraRodando = rodando;
    rodando = d.running;
    if (tipo !== null) {
      if (rodando) {
        status('RODANDO', 'bg-emerald-500/20 text-emerald-300 animate-pulse');
      } else if (paradoPorMim) {
        status('ENCERRADO', 'bg-amber-500/20 text-amber-300');
      } else if (d.exit_code === 0) {
        status('FINALIZADO', 'bg-sky-500/20 text-sky-300');
      } else {
        status(`ERRO (código ${d.exit_code})`, 'bg-red-500/20 text-red-300');
      }
    }
    atualizaBotoes();

    if (eraRodando && !rodando) {    // acabou de terminar
      paradoPorMim = false;
      if (d.saved) {
        $('sResumoTxt').textContent = `${d.saved.novas} ofertas desta busca. A lista de Produtos agora tem ${d.saved.total}.` + (d.saved.otimas ? ` ${d.saved.otimas} com Deal Score 75 ou mais.` : '') +
          (d.saved.abaixo_da_nota ? ` (${d.saved.abaixo_da_nota} ficaram de fora por estarem abaixo do Deal Score ${d.saved.min_score})` : '') +
          (d.saved.ignoradas ? ` (${d.saved.ignoradas} ignoradas por estarem descartadas)` : '');
        $('sResumo').classList.remove('hidden');
        carregar();                  // atualiza a aba Produtos (função do app.js)
      }
    }
  }

  async function iniciar(manual) {
    aviso('');
    const query = $('sQuery').value.trim();
    const sub = $('sSub').value;
    const url = $('sUrl').value.trim();

    if (tipo === 'busca' && !manual && !query) {
      aviso('Informe o produto que deseja buscar.'); $('sQuery').focus(); return;
    }
    if (tipo === 'categoria' && !manual) {
      if (!catSel) { aviso('Escolha uma categoria.'); return; }
      const cat = categorias && categorias.find(c => c.nome === catSel);
      if (cat && cat.subs && !sub) { aviso('Escolha a subcategoria.'); $('sSub').focus(); return; }
      if (catSel === custom && !url) { aviso('Cole a URL da categoria.'); $('sUrl').focus(); return; }
    }

    const abaUrl = $('sAbaUrl').value.trim();
    if (tipo === 'ofertas' && !manual) {
      if (!abaSel) { aviso('Escolha uma aba.'); return; }
      if (abaSel === custom && !abaUrl) { aviso('Cole a URL da aba.'); $('sAbaUrl').focus(); return; }
    }

    try {
      await post('/api/scraper/start', {
        tipo,
        aba: abaSel,
        aba_url: abaUrl,
        query,
        categoria: catSel,
        subcategoria: sub,
        url,
        min_discount: $('sMin').value,
        min_score: $('sMinScore').value,
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

  document.querySelectorAll('.sTipo').forEach(card => {
    card.addEventListener('click', () => mostrarTela(card.dataset.tipo));
  });
  $('sVoltar').addEventListener('click', mostrarEscolha);
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
