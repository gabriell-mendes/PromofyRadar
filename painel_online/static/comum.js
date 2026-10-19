/* Utilitários das páginas do painel online. */
const $ = (id) => document.getElementById(id);
const brl = (n) => Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

// Tudo é montado com textContent (nunca innerHTML): título, link e nome vêm de dados enviados por outros PCs.
function el(tag, cls, texto) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (texto != null) e.textContent = texto;
  return e;
}
const urlSegura = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

// O cookie de sessão vai sozinho (mesma origem). X-TechDrop é a proteção CSRF: ver auth.somente_painel.
async function api(caminho, corpo, metodo) {
  const post = corpo !== undefined || metodo === 'POST';
  const r = await fetch(caminho, {
    method: post ? 'POST' : 'GET',
    headers: post ? { 'X-TechDrop': '1', 'Content-Type': 'application/json' } : {},
    body: post ? JSON.stringify(corpo ?? {}) : undefined,
  });
  let dados = null;
  try { dados = await r.json(); } catch {}
  if (r.status === 401 && caminho !== '/api/login') { location.href = '/login'; throw new Error('Sessão expirada.'); }
  if (!r.ok) throw new Error((dados && typeof dados.detail === 'string' && dados.detail) || 'Erro ' + r.status);
  return dados;
}

async function sair() {
  try { await api('/api/logout', {}); } catch {}
  location.href = '/login';
}

// Barra lateral comum (igual à do painel local): logo, páginas, nome do usuário e Sair.
// Os ícones são caminhos fixos daqui; o nome do usuário entra sempre por textContent.
const ICONES = {
  ofertas: 'M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8',
  tokens: 'M21 2l-2 2m-7.6 7.6a5.5 5.5 0 1 1-7.8 7.8 5.5 5.5 0 0 1 7.8-7.8zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4',
};
const PAGINAS = [['ofertas', 'Ofertas', '/'], ['tokens', 'Meus tokens', '/tokens']];

function icone(d) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('class', 'w-4 h-4'); s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '2');
  s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round');
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', d); s.appendChild(p);
  return s;
}

async function cabecalho(paginaAtual) {
  const eu = await api('/api/eu');

  const logo = el('div', 'px-5 py-5 text-lg font-bold tracking-tight text-white', 'Tech');
  logo.appendChild(el('span', 'text-emerald-400', 'Drop'));

  const nav = el('nav', 'flex-1 px-3 space-y-1 text-sm');
  PAGINAS.forEach(([id, nome, href]) => {
    const a = el('a', 'flex items-center gap-3 px-3 py-2 rounded-lg ' + (id === paginaAtual ? 'bg-emerald-600/15 text-emerald-400' : 'text-slate-300 hover:bg-white/5'));
    a.href = href;
    a.append(icone(ICONES[id]), nome);
    nav.appendChild(a);
  });

  const rodape = el('div', 'p-4 border-t border-line text-xs');
  rodape.appendChild(el('p', 'text-slate-300 truncate', eu.nome));
  const btnSair = el('button', 'mt-2 w-full px-3 py-1.5 text-sm rounded-lg bg-bg border border-line hover:border-slate-500', 'Sair');
  btnSair.onclick = sair;
  rodape.appendChild(btnSair);
  rodape.appendChild(el('p', 'text-slate-500 mt-3', 'TechDrop Online'));

  $('sidebar').replaceChildren(logo, nav, rodape);

  // Celular: a barra lateral some e vira uma fileira de botões no topo.
  const mobile = $('navMobile'); mobile.replaceChildren();
  PAGINAS.forEach(([id, nome, href]) => {
    const a = el('a', 'px-4 py-2 rounded-full text-sm border ' + (id === paginaAtual ? 'bg-emerald-600 border-emerald-500 text-white' : 'bg-panel border-line text-slate-300'), nome);
    a.href = href;
    mobile.appendChild(a);
  });
  const sm = el('button', 'px-4 py-2 rounded-full text-sm border bg-panel border-line text-slate-300', 'Sair');
  sm.onclick = sair;
  mobile.appendChild(sm);
}
