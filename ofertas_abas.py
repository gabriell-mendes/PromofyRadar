"""Abas da página de Ofertas do Mercado Livre (https://www.mercadolivre.com.br/ofertas).

Arquivo SEM imports pesados, lido pelo scraper_ofertas.py e pelo techdrop_server.py.

O scraper NÃO usa URL fixa por aba: ele abre a página de Ofertas, lê o filtro que o
próprio site embute no HTML para cada aba (ex: promotion_type=lightning) e monta a
URL com ele. Assim, se o ML mudar os filtros, só o nome precisa continuar igual.

Para adicionar uma aba, escreva o nome exatamente como aparece no site.
"""

OFERTAS_URL = "https://www.mercadolivre.com.br/ofertas"

# Na ordem em que aparecem no site. A primeira é a página principal, sem clique.
ABAS = [
    "Todas as ofertas",
    "Ofertas relâmpago",
    "Preços Imbatíveis",
    "Outlet",
    "Celulares",
    "Notebooks",
    "Menos de R$100",
    "Internacional",
    "Tênis",
    "Fones",
    "TVs",
    "Ferramentas",
    "Smartwatches",
    "Supermercado",
    "Caixas de som",
    "Perfumes",
    "Moda",
    "Esportes e fitness",
]

# Categoria do painel (aba Produtos) de cada aba de Ofertas. Abas que misturam de tudo
# (Todas, Relâmpago, Outlet, Menos de R$100...) ficam de fora: o painel classifica
# esses produtos pelo título. Os nomes são as categorias oficiais do ML.
ABA_CATEGORIA = {
    "Celulares": "Celulares e Telefones",
    "Smartwatches": "Celulares e Telefones",
    "Notebooks": "Informática",
    "Fones": "Eletrônicos, Áudio e Vídeo",
    "TVs": "Televisores",
    "Caixas de som": "Eletrônicos, Áudio e Vídeo",
    "Tênis": "Moda",
    "Moda": "Moda",
    "Ferramentas": "Ferramentas",
    "Perfumes": "Beleza e Cuidado Pessoal",
    "Esportes e fitness": "Esportes e Fitness",
    "Supermercado": "Supermercado",
    "Internacional": "Internacional",
}

# Opção extra: o usuário cola a URL de uma aba que não está na lista
# (o carrossel do site tem abas que ainda não listei).
CUSTOM = "Colar URL"


def limpar_url(url: str) -> str:
    """Tira âncora e o parâmetro de página para podermos paginar depois."""
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    p = urlparse(url.strip().split("#")[0])
    query = [(k, v) for k, v in parse_qsl(p.query) if k != "page"]
    return urlunparse(p._replace(query=urlencode(query)))


def validar_escolha(aba: str, url_custom: str = "") -> str:
    """Devolve o nome da aba (ou a URL limpa, se for custom). ValueError se inválida."""
    if aba == CUSTOM:
        url = limpar_url(url_custom)
        if not url.startswith(OFERTAS_URL):
            raise ValueError(f"URL inválida: use uma URL que comece com {OFERTAS_URL}")
        return url
    if aba not in ABAS:
        raise ValueError(f"Aba desconhecida: {aba}")
    return aba
