/* ============ ESTADO ============ */
const ARQUIVOS = ['data/ofertas.json', 'data/ofertas.sample.json'];
const CHAVE_LS = 'ofertas_enviadas_v1';
let offers = [];                 // lista vinda do JSON
let descartados = [];            // vindos do servidor (data/descartados.json), com discarded_at
let diasDescarte = 7;            // quantos dias até apagar de vez (o servidor confirma)
let enviados = lerEnviados();    // { link: dataISO }  ("marcar como enviado": mensagem publicada à mão)
let telegram = { configurado: false };  // envio ao Telegram (TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env do servidor)
let painel = { configurado: false, url: null };  // envio ao painel online (PAINEL_URL no .env do servidor)
let afiliado = { configurado: false, matt_word: null, matt_tool: null };  // link de afiliado ML (AFILIADO_ML_MATT_WORD/TOOL no .env do servidor)
const selecionados = new Set();  // links marcados
const f = { status: 'todos', cat: 'todas', min: 0, minScore: 0, busca: '', ordem: 'score' };
let previewKey = null;

/* ============ UTIL ============ */
const $ = (id) => document.getElementById(id);
const brl = (n) => Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function lerEnviados() {
  try { return JSON.parse(localStorage.getItem(CHAVE_LS)) || {}; } catch { return {}; }
}
function salvarEnviados() {
  try { localStorage.setItem(CHAVE_LS, JSON.stringify(enviados)); } catch {}
}
const ehEnviado = (o) => !!enviados[o.link];
// Ofertas da lista que NÃO foram descartadas (as descartadas ficam só na aba Descartados)
const ativos = () => { const fora = new Set(descartados.map((d) => d.link)); return offers.filter((o) => !fora.has(o.link)); };

/* ============ DEAL SCORE ============ */
const FAIXAS_SCORE = [[75, 'Ótima', 'bg-emerald-500 text-white'], [50, 'Boa', 'bg-sky-500/30 text-sky-200'],
  [25, 'Regular', 'bg-amber-500/25 text-amber-200'], [0, 'Fraca', 'bg-slate-600/40 text-slate-300']];
const FLAGS_DEAL = { desconto_inflado: 'Desconto inflado', menor_preco_recente: 'Menor preço recente', preco_invalido: 'Preço inválido' };
const temScore = (o) => o.deal_score !== null && o.deal_score !== undefined;
function faixaScore(s) { return FAIXAS_SCORE.find(([min]) => s >= min) || FAIXAS_SCORE[FAIXAS_SCORE.length - 1]; }

function blocoScore(o) {
  if (!('deal_score' in o)) return '';   // oferta antiga, coletada antes do Deal Score
  const motivos = Array.isArray(o.deal_motivos) ? o.deal_motivos : [];
  const flags = (o.deal_flags || []).map((x) => `<span class="text-[10px] px-2 py-0.5 rounded ${x === 'desconto_inflado' || x === 'preco_invalido' ? 'bg-red-500/20 text-red-300' : 'bg-emerald-500/20 text-emerald-300'}">${esc(FLAGS_DEAL[x] || x)}</span>`).join('');
  const selo = temScore(o)
    ? `<span class="text-xs font-bold px-2 py-1 rounded ${faixaScore(o.deal_score)[2]}" title="Deal Score de 0 a 100">Deal ${o.deal_score} · ${faixaScore(o.deal_score)[1]}</span>`
    : `<span class="text-xs font-bold px-2 py-1 rounded bg-slate-700 text-slate-300">Sem nota</span>`;
  const conf = o.deal_confianca === 'alta' ? 'confiança alta' : o.deal_confianca === 'baixa' ? 'confiança baixa' : '';
  return `<div class="mt-2 flex flex-wrap items-center gap-2">${selo}${conf ? `<span class="text-[10px] text-slate-500">${conf}</span>` : ''}${flags}</div>
      ${motivos.length ? `<p class="text-[11px] text-slate-400 mt-1 clamp2" title="${esc(motivos.join(' | '))}">${esc(motivos[0])}</p>` : ''}`;
}

function toast(msg, ms = 4000) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.add('hidden'), ms);
}

async function api(url, body) {
  let r;
  try {
    r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-TechDrop': '1' }, body: JSON.stringify(body) });
  } catch { throw new Error('Servidor do TechDrop não encontrado. Abra pelo iniciar.bat'); }
  if (!r.ok) {
    let detalhe = '';
    try { const j = await r.json(); if (typeof j.detail === 'string') detalhe = j.detail; } catch {}
    throw new Error(detalhe || `Erro ${r.status}`);   // o servidor já explica o problema em português
  }
  return r.json();
}

function textoRestante(o) {
  const ms = new Date(o.discarded_at).getTime() + diasDescarte * 864e5 - Date.now();
  const dias = Math.ceil(ms / 864e5);
  if (dias <= 1) return ms <= 0 ? 'Apagando...' : 'Apaga em menos de 1 dia';
  return `Apaga em ${dias} dias`;
}

/* ============ SIDEBAR ============ */
const ICONS = {
  Dashboard: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  Produtos: 'M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8',
  Scraper: 'M4 17l6-6-6-6M12 19h8',
  Canais: 'M3 11v2l13 5V6L3 11zM19 8v8',
  Grupos: 'M17 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M10 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM21 20v-2a4 4 0 0 0-3-3.9M16 2.1a4 4 0 0 1 0 7.8',
  'Automações': 'M13 2L4 14h7l-1 8 9-12h-7z',
  Disparar: 'M22 2L11 13M22 2l-7 20-4-9-9-4z',
  'Histórico': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2',
  'Configurações': 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
  Admin: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
};
const VIEWS = { Produtos: 'produtos', Scraper: 'scraper' };  // abas que já funcionam
let viewAtual = 'produtos';

function renderNav() {
  $('nav').innerHTML = Object.entries(ICONS).map(([nome, d]) => {
    const view = VIEWS[nome];
    const ativo = view && view === viewAtual;
    const cls = ativo ? 'bg-emerald-600/15 text-emerald-400' : view ? 'text-slate-300 hover:bg-white/5 cursor-pointer' : 'text-slate-400 opacity-60';
    return `<div ${view ? `data-view="${view}"` : 'title="Em breve"'} class="flex items-center gap-3 px-3 py-2 rounded-lg ${cls}">
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>${nome}</div>`;
  }).join('');
  $('navMobile').innerHTML = Object.entries(VIEWS).map(([nome, view]) =>
    chip(view, nome, view === viewAtual, 'view')).join('');
}

function setView(view) {
  viewAtual = view;
  $('viewProdutos').classList.toggle('hidden', view !== 'produtos');
  $('viewScraper').classList.toggle('hidden', view !== 'scraper');
  try { history.replaceState(null, '', '#' + view); } catch {}
  renderNav();
  render();
  document.dispatchEvent(new CustomEvent('viewchange', { detail: view }));
}

/* ============ FILTROS ============ */
function visiveis() {
  const q = f.busca.trim().toLowerCase();
  const emDesc = f.status === 'descartado';
  let list = (emDesc ? descartados : ativos()).filter((o) =>
    (emDesc || f.status === 'todos' || (f.status === 'enviado') === ehEnviado(o)) &&
    (f.cat === 'todas' || categoriaDe(o) === f.cat) &&
    (o.discount || 0) >= f.min &&
    (f.minScore === 0 || (temScore(o) && o.deal_score >= f.minScore)) &&
    (!q || o.title.toLowerCase().includes(q))
  );
  if (f.ordem === 'score') list.sort((a, b) => (temScore(b) - temScore(a)) || ((b.deal_score || 0) - (a.deal_score || 0)) || (b.discount - a.discount));
  if (f.ordem === 'disc') list.sort((a, b) => b.discount - a.discount);
  if (f.ordem === 'asc') list.sort((a, b) => a.price - b.price);
  if (f.ordem === 'desc') list.sort((a, b) => b.price - a.price);
  return list;
}

/* ============ RENDER ============ */
function render() {
  // contadores de status
  const base = ativos();
  const nEnv = base.filter(ehEnviado).length;
  const cont = { todos: base.length, pendente: base.length - nEnv, enviado: nEnv, descartado: descartados.length };
  const abasS = [['todos', 'Todos'], ['pendente', 'Pendentes'], ['enviado', 'Enviados'], ['descartado', 'Descartados']];
  $('tabsStatus').innerHTML = abasS.map(([id, nome]) => chip(id, `${nome} (${cont[id]})`, f.status === id, 'status')).join('');

  // chips de categoria: só as que têm produtos, com contagem (respeita a aba de status)
  const baseCat = f.status === 'descartado' ? descartados
    : base.filter((o) => f.status === 'todos' || (f.status === 'enviado') === ehEnviado(o));
  const porCat = {};
  baseCat.forEach((o) => { const c = categoriaDe(o); porCat[c] = (porCat[c] || 0) + 1; });
  if (f.cat !== 'todas' && !porCat[f.cat]) f.cat = 'todas';   // categoria esvaziou: volta para Todas
  // mesma ordem da lista do Mercado Livre; só as categorias que têm produtos
  const ordemCat = [...CATEGORIAS_PAINEL.filter((c) => porCat[c]), ...(porCat[CATEGORIA_PADRAO] ? [CATEGORIA_PADRAO] : [])];
  $('listaCat').innerHTML = [['todas', 'Todas', baseCat.length], ...ordemCat.map((c) => [c, c, porCat[c]])]
    .map(([id, nome, n]) => itemCat(id, nome, n, f.cat === id)).join('');

  // cards
  const lista = visiveis();
  const emDesc = f.status === 'descartado';
  $('grid').innerHTML = lista.map(emDesc ? cardDescartado : card).join('');
  $('vazioTxt').textContent = emDesc ? `Nenhum produto descartado. Eles ficam aqui por ${diasDescarte} dias e depois são apagados.` : 'Nenhuma oferta para mostrar.';
  $('vazio').classList.toggle('hidden', lista.length > 0);

  // "Marcar todos" reflete o que está visível
  const todosMarcados = lista.length > 0 && lista.every((o) => selecionados.has(o.link));
  $('chkAll').checked = todosMarcados;

  // barra de lote
  $('lote').classList.toggle('hidden', selecionados.size === 0 || viewAtual !== 'produtos');
  $('loteN').textContent = selecionados.size;
  $('btnLoteEnviar').classList.toggle('hidden', emDesc);
  $('btnLoteDescartar').classList.toggle('hidden', emDesc);
  $('btnLotePainel').classList.toggle('hidden', emDesc);
  const pendentesPainel = base.filter((o) => !o.teste && !o.enviado_painel_em).length;
  $('btnPainel').textContent = pendentesPainel ? `Enviar ao painel (${pendentesPainel})` : 'Enviar ao painel';
  $('btnPainel').disabled = pendentesPainel === 0;
  $('btnLoteRestaurar').classList.toggle('hidden', !emDesc);
  $('btnLoteExcluir').classList.toggle('hidden', !emDesc);
  $('btnEsvaziar').classList.toggle('hidden', !emDesc || descartados.length === 0);
}

function chip(id, texto, ativo, tipo) {
  return `<button data-${tipo}="${id}" class="px-4 py-2 rounded-full text-sm border transition ${ativo ? 'bg-emerald-600 border-emerald-500 text-white' : 'bg-panel border-line text-slate-300 hover:border-slate-500'}">${texto}</button>`;
}

// Item da lista lateral de categorias (estilo Mercado Livre: nome + contagem em cinza)
function itemCat(id, nome, n, ativo) {
  return `<button data-cat="${esc(id)}" class="block w-full text-left py-1 text-sm ${ativo ? 'text-emerald-400 font-semibold' : 'text-slate-300 hover:text-white'}">${esc(nome)} <span class="text-slate-500 font-normal">(${n})</span></button>`;
}

function card(o) {
  const env = ehEnviado(o);
  const sel = selecionados.has(o.link);
  const temDesc = (o.discount || 0) > 0;
  const img = o.image
    ? `<img src="${esc(o.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" class="w-full h-full object-contain p-3">`
    : `<svg class="w-12 h-12 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>`;
  return `
  <div class="bg-card border ${sel ? 'border-emerald-500' : 'border-line'} rounded-xl overflow-hidden flex flex-col">
    <div class="relative h-44 bg-white/5 flex items-center justify-center">
      <input type="checkbox" data-sel="${esc(o.link)}" ${sel ? 'checked' : ''} class="absolute top-3 left-3">
      <span class="absolute top-3 right-3 text-[10px] font-bold tracking-wide px-2 py-1 rounded ${env ? 'bg-sky-500/20 text-sky-300' : 'bg-amber-500/20 text-amber-300'}">${env ? 'ENVIADO' : 'PENDENTE'}</span>
      ${temDesc ? `<span class="absolute bottom-3 left-3 text-xs font-bold px-2 py-1 rounded bg-emerald-500 text-white">-${Math.round(o.discount)}%</span>` : ''}
      <span class="absolute bottom-3 right-3 text-[10px] px-2 py-1 rounded bg-black/60 text-slate-200">${esc(categoriaDe(o))}</span>
      ${o.teste ? '<span class="absolute top-10 right-3 text-[10px] font-bold px-2 py-1 rounded bg-fuchsia-500/30 text-fuchsia-200">TESTE</span>' : ''}
      ${o.enviado_painel_em ? '<span class="absolute top-10 left-3 text-[10px] font-bold tracking-wide px-2 py-1 rounded bg-sky-500/20 text-sky-300" title="Já enviada ao painel online">NO PAINEL</span>' : ''}
      ${img}
    </div>
    <div class="p-4 flex flex-col flex-1">
      <a href="${esc(o.link)}" target="_blank" rel="noopener" class="clamp2 text-sm font-medium text-slate-100 hover:text-emerald-400 min-h-[2.5rem]">${esc(o.title)}</a>
      <div class="mt-3 flex items-baseline gap-2">
        <span class="text-xl font-bold text-white">${brl(o.price)}</span>
        ${temDesc ? `<span class="text-sm text-slate-500 line-through">${brl(o.old_price)}</span>` : ''}
      </div>
      ${blocoScore(o)}
      <p class="text-xs text-slate-400 mt-1 clamp2">${esc(o.installment)}</p>
      <div class="mt-auto pt-4 flex gap-2">
        <button data-prev="${esc(o.link)}" class="flex-1 px-3 py-2 text-sm rounded-lg ${env ? 'bg-bg border border-line hover:border-slate-500' : 'bg-emerald-600 hover:bg-emerald-500 text-white'}">${env ? 'Ver preview' : 'Preview &amp; Enviar'}</button>
        ${env ? `<button data-undo="${esc(o.link)}" title="Voltar para pendente" class="px-3 py-2 text-sm rounded-lg bg-bg border border-line hover:border-slate-500">Desfazer</button>` : ''}
        <button data-discard="${esc(o.link)}" title="Descartar (fica ${diasDescarte} dias na aba Descartados)" class="px-3 py-2 rounded-lg bg-bg border border-line text-slate-400 hover:text-red-300 hover:border-red-500/50">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6"/></svg>
        </button>
      </div>
    </div>
  </div>`;
}

function cardDescartado(o) {
  const sel = selecionados.has(o.link);
  const temDesc = (o.discount || 0) > 0;
  return `
  <div class="bg-card border ${sel ? 'border-emerald-500' : 'border-line'} rounded-xl overflow-hidden flex flex-col opacity-80">
    <div class="p-4 flex flex-col flex-1">
      <div class="flex items-start gap-3">
        <input type="checkbox" data-sel="${esc(o.link)}" ${sel ? 'checked' : ''} class="mt-1 shrink-0">
        <a href="${esc(o.link)}" target="_blank" rel="noopener" class="clamp2 text-sm font-medium text-slate-100 hover:text-emerald-400 flex-1">${esc(o.title)}</a>
        <span class="text-[10px] font-bold tracking-wide px-2 py-1 rounded bg-red-500/20 text-red-300 shrink-0">DESCARTADO</span>
      </div>
      <div class="mt-3 flex items-baseline gap-2">
        <span class="text-lg font-bold text-white">${brl(o.price)}</span>
        ${temDesc ? `<span class="text-sm text-slate-500 line-through">${brl(o.old_price)}</span><span class="text-xs font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">-${Math.round(o.discount)}%</span>` : ''}
      </div>
      <p class="text-xs text-amber-300/80 mt-2">${textoRestante(o)}</p>
      <div class="mt-auto pt-4">
        <div class="flex gap-2">
          <button data-restore="${esc(o.link)}" class="flex-1 px-3 py-2 text-sm rounded-lg bg-bg border border-line hover:border-emerald-500 hover:text-emerald-300">Restaurar</button>
          <button data-purge="${esc(o.link)}" title="Apagar de vez" class="px-3 py-2 rounded-lg bg-bg border border-line text-slate-400 hover:text-red-300 hover:border-red-500/50">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6"/></svg>
          </button>
        </div>
      </div>
    </div>
  </div>`;
}

/* ============ MENSAGEM (modelo simples, ajuste à vontade) ============ */
/* Acrescenta matt_word/matt_tool ao link, se o .env do servidor tiver o afiliado configurado. */
function linkComAfiliado(link) {
  if (!afiliado.configurado) return link;
  try {
    const u = new URL(link);
    u.searchParams.set('matt_word', afiliado.matt_word);
    u.searchParams.set('matt_tool', afiliado.matt_tool);
    return u.toString();
  } catch {
    return link;
  }
}

function mensagem(o) {
  const linhas = [`OFERTA: ${o.title}`, ''];
  if (o.discount > 0) linhas.push(`De ${brl(o.old_price)} por ${brl(o.price)} (-${Math.round(o.discount)}%)`);
  else linhas.push(`Por ${brl(o.price)}`);
  if (o.installment && o.installment !== 'Consulte no site') linhas.push(o.installment);
  linhas.push('', linkComAfiliado(o.link));
  return linhas.join('\n');
}

/* ============ AÇÕES ============ */
function marcarEnviado(links) {
  const agora = new Date().toISOString();
  links.forEach((l) => { enviados[l] = agora; selecionados.delete(l); });
  salvarEnviados();
  render();
}

async function descartar(links) {
  const alvo = ativos().filter((o) => links.includes(o.link));
  if (!alvo.length) return;
  try {
    await api('/api/descartar', { offers: alvo });
    const sair = new Set(links);
    offers = offers.filter((o) => !sair.has(o.link));   // o servidor também tirou do ofertas.json
    links.forEach((l) => selecionados.delete(l));
    await carregarDescartados();
    toast(`${alvo.length} descartado(s). Ficam ${diasDescarte} dias na aba Descartados.`);
  } catch (e) { toast(e.message); }
}

async function restaurar(links) {
  try {
    await api('/api/restaurar', { links });
    links.forEach((l) => selecionados.delete(l));
    await carregarDescartados();
    await carregar();   // a oferta voltou para data/ofertas.json
    toast(`${links.length} restaurado(s) para Produtos.`);
  } catch (e) { toast(e.message); }
}

function confirmar(texto, { titulo = 'Apagar permanentemente?', botao = 'Apagar de vez', perigo = true } = {}) {
  return new Promise((resolve) => {
    $('confirmTitulo').textContent = titulo;
    $('confirmSim').textContent = botao;
    $('confirmSim').className = 'px-3 py-2 text-sm rounded-lg text-white ' + (perigo ? 'bg-red-600 hover:bg-red-500' : 'bg-emerald-600 hover:bg-emerald-500');
    $('confirmTxt').textContent = texto;
    $('confirmModal').classList.remove('hidden');
    const fim = (v) => { $('confirmModal').classList.add('hidden'); $('confirmSim').onclick = $('confirmNao').onclick = null; resolve(v); };
    $('confirmSim').onclick = () => fim(true);
    $('confirmNao').onclick = () => fim(false);
  });
}

async function excluirDefinitivo(links, texto) {
  if (!links.length) return;
  if (!(await confirmar(texto))) return;
  try {
    const r = await api('/api/descartados/excluir', { links });
    links.forEach((l) => selecionados.delete(l));
    await carregarDescartados();
    toast(`${r.excluidos} produto(s) apagado(s) de vez.`);
  } catch (e) { toast(e.message); }
}

/* Envio ao painel online. `links` = só essas; null = todas as ainda não enviadas. */
async function enviarAoPainel(links) {
  if (!painel.configurado) {
    toast('Envio não configurado. Preencha PAINEL_URL e PAINEL_TOKEN no .env e reinicie o painel.', 8000);
    return;
  }
  const alvo = ativos().filter((o) => !o.teste && (links ? links.includes(o.link) : !o.enviado_painel_em));
  const testes = links ? ativos().filter((o) => o.teste && links.includes(o.link)).length : 0;
  if (!alvo.length) { toast('Nenhuma oferta para enviar' + (testes ? ' (ofertas de teste não são enviadas).' : '.')); return; }
  const jaForam = alvo.filter((o) => o.enviado_painel_em).length;
  const texto = `Enviar ${alvo.length} oferta(s) para ${new URL(painel.url).host}?` +
    (jaForam ? ` ${jaForam} já foram enviadas antes: serão atualizadas.` : '') +
    (testes ? ` ${testes} de teste ficam de fora.` : '');
  if (!(await confirmar(texto, { titulo: 'Enviar ao painel online?', botao: 'Enviar', perigo: false }))) return;

  $('btnPainel').disabled = $('btnLotePainel').disabled = true;
  toast('Enviando ao painel...', 60000);
  try {
    const r = await api('/api/painel/enviar', links ? { links: alvo.map((o) => o.link) } : {});
    let msg = `Enviado: ${r.criadas} nova(s), ${r.atualizadas} atualizada(s)`;
    if (r.ignoradas) msg += `, ${r.ignoradas} recusada(s) pelo painel (ex.: ${r.detalhes_ignoradas[0].titulo}: ${r.detalhes_ignoradas[0].motivo})`;
    await carregar();
    toast(msg + '.', r.ignoradas ? 10000 : 5000);
  } catch (e) {
    await carregar();   // pode ter chegado parte das ofertas antes do erro
    toast(e.message, 10000);
  } finally {
    $('btnLotePainel').disabled = false;
    render();
  }
}

async function carregarTelegramStatus() {
  try { telegram = await (await fetch('/api/telegram/status')).json(); } catch { telegram = { configurado: false }; }
}

/* Envia ao Telegram o texto do preview (já revisado/editado por você) e marca como enviado. */
async function enviarAoTelegram() {
  if (!telegram.configurado) {
    toast('Telegram não configurado. Preencha TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env e reinicie o painel.', 8000);
    return;
  }
  const texto = $('preview').textContent.trim();
  if (!texto || !previewKey) return;
  if (!(await confirmar('Publicar esta mensagem no grupo do Telegram?', { titulo: 'Enviar ao Telegram?', botao: 'Enviar', perigo: false }))) return;
  $('mTelegram').disabled = true;
  try {
    await api('/api/telegram/enviar', { texto });
    marcarEnviado([previewKey]);
    fecharPreview();
    toast('Mensagem enviada ao Telegram.');
  } catch (e) { toast(e.message, 10000); }
  finally { $('mTelegram').disabled = false; }
}

async function carregarPainelStatus() {
  try { painel = await (await fetch('/api/painel/status')).json(); } catch { painel = { configurado: false, url: null }; }
}

async function carregarAfiliadoStatus() {
  try { afiliado = await (await fetch('/api/afiliado/status')).json(); }
  catch { afiliado = { configurado: false, matt_word: null, matt_tool: null }; }
}

function abrirPreview(link) {
  const o = ativos().find((x) => x.link === link);
  if (!o) return;
  previewKey = link;
  $('preview').textContent = mensagem(o);
  $('mEnviar').classList.toggle('hidden', ehEnviado(o));
  $('modal').classList.remove('hidden');
}
function fecharPreview() { $('modal').classList.add('hidden'); previewKey = null; }

/* ============ EVENTOS ============ */
document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-status],[data-cat],[data-prev],[data-undo],[data-view],[data-discard],[data-restore],[data-purge]');
  if (!t) return;
  if (t.dataset.view) setView(t.dataset.view);
  else if (t.dataset.status) { f.status = t.dataset.status; selecionados.clear(); render(); }
  else if (t.dataset.cat) { f.cat = t.dataset.cat; selecionados.clear(); render(); }
  else if (t.dataset.discard) descartar([t.dataset.discard]);
  else if (t.dataset.restore) restaurar([t.dataset.restore]);
  else if (t.dataset.purge) excluirDefinitivo([t.dataset.purge], 'Apagar este produto de vez? Não dá para desfazer.');
  else if (t.dataset.prev) abrirPreview(t.dataset.prev);
  else if (t.dataset.undo) { delete enviados[t.dataset.undo]; salvarEnviados(); render(); }
});

$('grid').addEventListener('change', (e) => {
  const link = e.target.dataset.sel;
  if (!link) return;
  e.target.checked ? selecionados.add(link) : selecionados.delete(link);
  render();
});

$('chkAll').addEventListener('change', (e) => {
  const lista = visiveis();
  lista.forEach((o) => (e.target.checked ? selecionados.add(o.link) : selecionados.delete(o.link)));
  render();
});

$('minRange').addEventListener('input', (e) => { f.min = Number(e.target.value); $('minLabel').textContent = f.min + '%'; render(); });
$('minScoreRange').addEventListener('input', (e) => { f.minScore = Number(e.target.value); $('minScoreLabel').textContent = f.minScore; render(); });
$('busca').addEventListener('input', (e) => { f.busca = e.target.value; render(); });
$('ordem').addEventListener('change', (e) => { f.ordem = e.target.value; render(); });

$('btnLoteEnviar').addEventListener('click', () => marcarEnviado([...selecionados]));
$('btnLoteDescartar').addEventListener('click', () => descartar([...selecionados]));
$('btnLotePainel').addEventListener('click', () => enviarAoPainel([...selecionados]));
$('btnPainel').addEventListener('click', () => enviarAoPainel(null));
$('btnLoteRestaurar').addEventListener('click', () => restaurar([...selecionados]));
$('btnLoteExcluir').addEventListener('click', () => excluirDefinitivo([...selecionados], `Apagar ${selecionados.size} produto(s) de vez? Não dá para desfazer.`));
$('btnEsvaziar').addEventListener('click', () => excluirDefinitivo(descartados.map((d) => d.link), `Apagar TODOS os ${descartados.length} produtos descartados de vez? Não dá para desfazer.`));
$('btnLoteLimpar').addEventListener('click', () => { selecionados.clear(); render(); });

$('mCancelar').addEventListener('click', fecharPreview);
$('modal').addEventListener('click', (e) => { if (e.target === $('modal')) fecharPreview(); });
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  if (!$('confirmModal').classList.contains('hidden')) $('confirmNao').click(); else fecharPreview();
});
$('mTelegram').addEventListener('click', enviarAoTelegram);
$('mEnviar').addEventListener('click', () => { if (previewKey) marcarEnviado([previewKey]); fecharPreview(); });
$('mCopiar').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText($('preview').textContent); $('mCopiar').textContent = 'Copiado'; setTimeout(() => ($('mCopiar').textContent = 'Copiar texto'), 1500); } catch {}
});

/* ============ CARREGAR DADOS ============ */
function aplicarDados(json, fonte) {
  const arr = Array.isArray(json) ? json : (json.items || json.offers || []);
  offers = arr.filter((o) => o && o.link && o.title).map((o) => ({ ...o, price: Number(o.price) || 0, old_price: Number(o.old_price) || 0, discount: Number(o.discount) || 0, ...('deal_score' in o ? { deal_score: o.deal_score === null ? null : Number(o.deal_score) } : {}) }));
  selecionados.clear();
  $('fonte').textContent = `${offers.length} ofertas carregadas`;
  render();
}

async function carregar() {
  for (const arq of ARQUIVOS) {
    try {
      const r = await fetch(`${arq}?t=${Date.now()}`);
      if (!r.ok) continue;
      const nome = arq.includes('sample') ? `${arq} (dados de exemplo)` : arq;
      aplicarDados(await r.json(), nome);
      return;
    } catch { /* tenta o próximo */ }
  }
  $('fonte').textContent = 'Nenhum JSON encontrado (rode via servidor local ou use "Carregar JSON")';
  render();
}

async function carregarDescartados() {
  try {
    const r = await fetch(`/api/descartados?t=${Date.now()}`);
    if (!r.ok) throw new Error(r.status);
    const j = await r.json();
    descartados = j.items || [];
    diasDescarte = j.dias || 7;
  } catch { descartados = []; }   // sem servidor: aba Descartados fica vazia
  render();
}

$('btnRecarregar').addEventListener('click', () => { carregar(); carregarDescartados(); });
$('fileInput').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try { aplicarDados(JSON.parse(await file.text()), file.name); }
  catch { $('fonte').textContent = 'JSON inválido'; }
  e.target.value = '';
});

const hash = location.hash.replace('#', '');
setView(Object.values(VIEWS).includes(hash) ? hash : 'produtos');
carregar();
carregarDescartados();
carregarPainelStatus();
carregarTelegramStatus();
carregarAfiliadoStatus();
