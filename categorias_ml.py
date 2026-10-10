"""Categorias do Mercado Livre usadas pelo scraper por categoria.

Fica num arquivo separado e SEM imports pesados (nada de Playwright) para que
duas partes do projeto leiam a mesma lista:
- scraper_categoria.py (o scraper)
- techdrop_server.py   (o painel, que mostra os botões de categoria)

Para adicionar ou corrigir uma categoria, mexa só aqui.
"""

BASE = "https://lista.mercadolivre.com.br"

# Nome exibido -> slug da URL em lista.mercadolivre.com.br.
# ATENÇÃO: confira cada slug no navegador na primeira vez (o ML pode renomear).
CATEGORIAS = {
    "Supermercado": "supermercado",
    "Tecnologia": None,  # tem submenu, ver TECNOLOGIA_SUB
    "Casa e Móveis": "casa-moveis-decoracao",
    "Eletrodomésticos": "eletrodomesticos",
    "Esportes e Fitness": "esportes-fitness",
    "Ferramentas": "ferramentas",
    "Construção": "construcao",
    "Indústria e Comércio": "industria-comercio",
    "Pet Shop": "animais",
    "Saúde": "saude",
    "Acessórios para Veículos": "acessorios-veiculos",
    "Beleza e Cuidado Pessoal": "beleza-cuidado-pessoal",
    "Moda": "calcados-roupas-bolsas",
    "Bebês": "bebes",
    "Brinquedos": "brinquedos-hobbies",
    "Livros": "livros-revistas-comics",
}

# A categoria Tecnologia tem submenu no site.
TECNOLOGIA_SUB = {
    "Celulares e Telefones": "celulares-telefones",
    "Informática": "informatica",
    "Eletrônicos, Áudio e Vídeo": "eletronicos-audio-video",
    "Games": "games",
    "Câmeras e Acessórios": "cameras-acessorios",
    "Televisores": "eletronicos-audio-video/televisores",  # confira no navegador na 1ª vez
}

# Opção extra: o usuário cola a URL de qualquer categoria.
CUSTOM = "Colar URL"

# Fora de propósito: Veículos e Imóveis (classificados, sem preço "de/por"),
# Mais vendidos e Lojas oficiais (layout diferente), Internacional e
# Produtos Sustentáveis (adicione depois se fizer sentido para o negócio).


def limpar_url(url: str) -> str:
    """Tira query string, âncora e paginação antiga para podermos montar as páginas."""
    url = url.strip().split("#")[0].split("?")[0].rstrip("/")
    return url.split("_Desde_")[0].rstrip("_")


def montar_url(categoria: str, subcategoria: str = "", url_custom: str = "") -> str:
    """Devolve a URL base da categoria. Levanta ValueError com mensagem clara se inválida."""
    if categoria == CUSTOM:
        url = limpar_url(url_custom)
        if not url.startswith(BASE):
            raise ValueError(f"URL inválida: use uma URL de {BASE.replace('https://', '')}")
        return url
    if categoria not in CATEGORIAS:
        raise ValueError(f"Categoria desconhecida: {categoria}")
    slug = CATEGORIAS[categoria]
    if slug is None:  # Tecnologia: precisa de subcategoria
        if subcategoria not in TECNOLOGIA_SUB:
            raise ValueError("Escolha a subcategoria de Tecnologia")
        slug = TECNOLOGIA_SUB[subcategoria]
    return f"{BASE}/{slug}"


def categoria_painel(categoria: str, subcategoria: str = ""):
    """Categoria do filtro da aba Produtos para gravar nos produtos coletados.

    Os filtros do painel usam os mesmos nomes do menu do Mercado Livre, com as
    subcategorias de Tecnologia no lugar de "Tecnologia" (ver categorias.js).
    None quando não dá para saber (ex: URL colada).
    """
    if categoria == "Tecnologia":
        return subcategoria if subcategoria in TECNOLOGIA_SUB else None
    return categoria if categoria in CATEGORIAS else None
