/* ============ CATEGORIAS DOS PRODUTOS (as do menu do Mercado Livre) ============
 * O filtro da aba Produtos usa o menu "Categorias" do ML. A categoria Tecnologia, que
 * no site tem submenu, entra aqui já aberta: Celulares e Telefones, Informática,
 * Câmeras e Acessórios, Games, Eletrônicos, Áudio e Vídeo e Televisores.
 *
 * A categoria de cada oferta é decidida assim:
 *   1. Se o scraper já sabe (coleta por categoria ou por aba de Ofertas), o servidor
 *      grava o campo "category" na oferta e ele vale sempre (é o caso mais confiável).
 *   2. Senão, uma regra SIMPLES de palavras-chave no título (REGRAS_CATEGORIA). Sem IA.
 *   3. Se nenhuma regra bater, "Outros".
 *
 * COMO AJUSTAR AS REGRAS: edite as listas abaixo. Cada item é um pedaço de regex
 * aplicado ao título sem acento e em minúsculas, sempre no INÍCIO de uma palavra:
 *   'notebook'  pega "notebook" e "notebooks"
 *   'tv\\b'     só a palavra "tv" (o \\b evita pegar "tvs" ou "tvbox" por engano)
 * A ORDEM importa: a primeira categoria que bater ganha. Por isso as mais
 * específicas ficam antes (ex: "carregador veicular" cai em Veículos).
 *
 * Os nomes precisam ser iguais aos do categorias_ml.py (o servidor grava esses nomes).
 */

// Ordem do menu do ML (Tecnologia aberta nas subcategorias).
const CATEGORIAS_PAINEL = [
  'Supermercado',
  'Celulares e Telefones', 'Informática', 'Câmeras e Acessórios', 'Games', 'Eletrônicos, Áudio e Vídeo', 'Televisores',
  'Casa e Móveis', 'Eletrodomésticos', 'Esportes e Fitness', 'Ferramentas', 'Construção', 'Indústria e Comércio',
  'Pet Shop', 'Saúde', 'Acessórios para Veículos', 'Beleza e Cuidado Pessoal', 'Moda', 'Bebês', 'Brinquedos',
  'Livros', 'Internacional',
];

const CATEGORIA_PADRAO = 'Outros';

const REGRAS_CATEGORIA = [
  ['Bebês', ['bebe', 'fralda', 'mamadeira', 'chupeta', 'berco', 'babador']],
  ['Pet Shop', ['cachorro', 'gatos?\\b', 'racao', 'pet\\b', 'coleira', 'areia higienica', 'petisco', 'aquario']],
  ['Acessórios para Veículos', [
    'pneu', 'automotiv', 'veicular', 'para-brisa', 'capa de banco', 'farol', 'oleo (de )?motor', 'capacete',
    'camera de re', 'motoqueiro', 'moto\\b', 'carro\\b',
  ]],
  // Regras curtas e específicas que precisam ganhar de palavras mais genéricas (ex: 'wifi', 'sapato')
  ['Indústria e Comércio', ['maquininha', 'codigo de barras']],
  ['Casa e Móveis', ['sapateira', 'organizador', 'varal']],
  ['Games', ['playstation', 'ps[45]\\b', 'xbox', 'nintendo', 'console', 'gamepad', 'joystick', 'fliperama', 'video ?game']],
  ['Televisores', ['smart tv', 'televisao', 'televisor', 'tv\\b(?! (box|stick))']],
  ['Câmeras e Acessórios', ['camera', 'gopro', 'tripe', 'lente', 'filmadora']],
  ['Celulares e Telefones', [
    'celular', 'smartphone', 'iphone', 'galaxy', 'xiaomi', 'redmi', 'motorola', 'poco\\b', 'smartwatch', 'smart ?band',
    'smart watch', 'relogio inteligente', 'capinha', 'pelicula', 'carregador', 'power ?bank', 'telefone',
  ]],
  ['Informática', [
    'notebook', 'laptop', 'macbook', 'computador', 'pc\\b', 'ssd', 'nvme', 'hd\\b', 'hd externo', 'memoria ram',
    'placa de video', 'placa mae', 'processador', 'ryzen', 'intel core', 'monitor', 'teclado', 'mouse', 'webcam',
    'roteador', 'repetidor', 'switch', 'gigabit', 'ethernet', 'impressora', 'toner', 'cartucho', 'pen ?drive',
    'cartao de memoria', 'gabinete', 'fonte atx', 'hub usb', 'cabo (usb|hdmi|lightning|de rede)', 'hdmi', 'wi-?fi',
    'tablet', 'ipad', 'kindle', 'software', 'antivirus', 'nobreak', 'estabilizador',
  ]],
  ['Ferramentas', [
    'furadeira', 'parafusadeira', 'chave de fenda', 'chave inglesa', 'alicate', 'martelo', 'serra\\b', 'esmerilhadeira',
    'trena', 'ferramenta', 'rocadeira', 'pistola de pintura', 'solda', 'lixadeira', 'nivel a laser', 'compressor',
    'jogo de chaves', 'soquete', 'broca',
  ]],
  ['Construção', [
    'torneira', 'chuveiro', 'sifao', 'vaso sanitario', 'tintas?\\b', 'piso', 'argamassa', 'disjuntor',
    'fio (eletrico|flexivel)', 'cabo flexivel', 'registro', 'cimento', 'azulejo', 'porcelanato', 'fechadura',
  ]],
  ['Eletrônicos, Áudio e Vídeo', [
    'fones?\\b', 'headset', 'airpods', 'bluetooth', 'caixa de som', 'soundbar', 'alexa', 'echo dot', 'microfone',
    'projetor', 'amplificador', 'drone', 'tv (box|stick)', 'suporte (para|de) tv', 'antena', 'equipamento para dj',
  ]],
  ['Eletrodomésticos', [
    'geladeira', 'refrigerador', 'fogao', 'cooktop', 'micro-?ondas', 'air ?fryer', 'fritadeira', 'liquidificador',
    'batedeira', 'cafeteira', 'aspirador', 'ventilador', 'ar condicionado', 'lava e seca', 'maquina de lavar',
    'lavadora', 'ferro de passar', 'purificador', 'climatizador', 'sanduicheira', 'forno eletrico', 'bebedouro',
    'multiprocessador', 'chaleira eletrica',
  ]],
  ['Esportes e Fitness', [
    'halter', 'anilha', 'bicicleta', 'bike\\b', 'esteira', 'whey', 'creatina', 'suplemento', 'bola de', 'luva de boxe',
    'corda de pular', 'yoga', 'kimono', 'caneleira', 'chuteira', 'patins', 'skate', 'barraca', 'camping', 'pesca',
    'elastico', 'musculacao', 'pre-?treino', 'cicloergometro',
  ]],
  ['Moda', [
    'camiseta', 'camisa', 'calca', 'bermuda', 'jaqueta', 'moletom', 'vestido', 'blusa', 'tenis', 'sapato', 'sandalia',
    'chinelo', 'botas?\\b', 'bolsa', 'mochila', 'cueca', 'meias?\\b', 'biquini', 'sunga', 'cinto', 'oculos', 'legging',
    'shorts?\\b', 'polo\\b', 'regata', 'casaco', 'carteira', 'pijama', 'lingerie', 'sutia', 'relogio', 'pulseira',
    'colar\\b', 'brinco', 'anel\\b', 'alianca', 'joia', 'conjunto (feminino|masculino)',
  ]],
  ['Beleza e Cuidado Pessoal', [
    'perfume', 'colonia', 'shampoo', 'condicionador', 'hidratante', 'creme (facial|para|hidratante)', 'protetor solar',
    'maquiagem', 'batom', 'esmalte', 'secador de cabelo', 'prancha', 'barbeador', 'aparador de (pelos|barba|cabelo)',
    'desodorante', 'sabonete', 'skincare', 'serum', 'mascara capilar', 'escova (alisadora|secadora)', 'depilador',
  ]],
  ['Saúde', [
    'vitamina', 'multivitaminico', 'termometro', 'oximetro', 'tensiometro', 'medidor de pressao', 'curativo',
    'massageador', 'colageno', 'omega 3', 'probiotico', 'glicosimetro', 'capsula', 'coenzima', 'magnesio', 'curcuma',
    'nac\\b', 'feno grego', 'arginina', 'formula exclusiva', '\\d+ ?mg\\b', 'irrigador oral',
  ]],
  ['Brinquedos', ['brinquedo', 'lego', 'boneca', 'quebra-cabeca', 'pelucia', 'jogo de tabuleiro', 'nerf', 'hot wheels', 'massinha', 'colecionavel', 'action figure']],
  ['Livros', ['livro', 'hq\\b', 'historia em quadrinhos']],
  ['Indústria e Comércio', ['maquininha', 'codigo de barras', 'balanca comercial', 'empilhadeira', 'industrial', 'gondola', 'expositor', 'etiquetadora', 'epi\\b', 'luva de seguranca', 'botons']],
  ['Casa e Móveis', [
    'sofa', 'cama\\b', 'colchao', 'travesseiro', 'mesa', 'cadeira', 'poltrona', 'estante', 'guarda-?roupa', 'armario',
    'cortina', 'tapete', 'lencol', 'toalha', 'edredom', 'organizador', 'prateleira', 'luminaria', 'abajur', 'decoracao',
    'lixeira', 'panela', 'jogo de cama', 'cabideiro', 'rack\\b', 'escrivaninha', 'cozinha', 'banheiro', 'quarto',
    'garrafa termica', 'cesto', 'cabide', 'banheira', 'pote', 'talher', 'copo', 'prato', 'lampada', 'sapateira', 'varal',
  ]],
  ['Supermercado', [
    'cafe\\b', 'arroz', 'feijao', 'azeite', 'leite', 'chocolate', 'biscoito', 'detergente', 'sabao', 'amaciante',
    'papel higienico', 'macarrao', 'molho', 'cerveja', 'vinho', 'refrigerante', 'agua mineral', 'acucar', 'farinha',
    'snack', 'sorvete',
  ]],
];

const semAcento = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// Compila uma vez: cada categoria vira uma regex "\b(?:palavra1|palavra2|...)"
const REGRAS_COMPILADAS = REGRAS_CATEGORIA.map(([nome, palavras]) => [nome, new RegExp('\\b(?:' + palavras.join('|') + ')')]);

const _cacheCategoria = new WeakMap();

function categoriaDe(o) {
  // categoria gravada pelo scraper (só vale se for uma das do painel; nomes antigos caem na regra)
  if (o.category && CATEGORIAS_PAINEL.includes(o.category)) return o.category;
  if (_cacheCategoria.has(o)) return _cacheCategoria.get(o);
  const titulo = semAcento(o.title);
  const achou = REGRAS_COMPILADAS.find(([, re]) => re.test(titulo));
  const cat = achou ? achou[0] : CATEGORIA_PADRAO;
  _cacheCategoria.set(o, cat);
  return cat;
}
