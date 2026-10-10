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

// Cabeçalho comum: nome do usuário, links e botão Sair.
async function cabecalho(paginaAtual) {
  const box = $('menu');
  const eu = await api('/api/eu');
  const link = (href, texto, ativo) => {
    const a = el('a', 'text-sm ' + (ativo ? 'text-emerald-400' : 'text-slate-300 hover:text-white'), texto);
    a.href = href;
    return a;
  };
  box.replaceChildren(
    link('/', 'Ofertas', paginaAtual === 'ofertas'),
    link('/tokens', 'Meus tokens', paginaAtual === 'tokens'),
    el('span', 'text-xs text-slate-500', eu.nome),
  );
  const b = el('button', 'px-3 py-1.5 text-sm rounded-lg bg-panel border border-line hover:border-slate-500', 'Sair');
  b.onclick = sair;
  box.appendChild(b);
}
