"""Liga o Deal Score (deal_score.py) ao historico (historico.py) para uma coleta.

Usado pelos scrapers: depois de extrair os itens, `pontuar` calcula a nota de
cada oferta que vai para o painel e so entao grava os precos de hoje no
historico (assim a nota de hoje nunca compara o produto com ele mesmo).

`vistos` sao TODOS os itens lidos na coleta, inclusive os que o filtro de
desconto minimo deixou de fora. Eles formam o "grupo" da mediana e alimentam o
historico. Sem isso, filtrar por desconto mudaria a mediana.
"""

from __future__ import annotations

from datetime import date

from deal_score import avaliar
from historico import chave_produto, obter, registrar


def pontuar(resultados: list[dict], vistos: list[dict], hoje: date | None = None, db=None) -> list[dict]:
    hoje = hoje or date.today()
    precos_grupo = [v["price"] for v in vistos if v.get("price")]
    chaves = {chave_produto(v["link"]) for v in vistos} | {chave_produto(r["link"]) for r in resultados}
    hist = obter(chaves, antes_de=hoje, db=db)

    for r in resultados:
        anunciado = r.get("old_price") if (r.get("old_price") or 0) > (r.get("price") or 0) else None
        av = avaliar(r.get("price"), anunciado, precos_grupo, hist.get(chave_produto(r["link"]), []))
        r["deal_score"] = av["score"]
        r["deal_confianca"] = av["confianca"]
        r["deal_motivos"] = av["motivos"]
        r["deal_flags"] = av["flags"]

    registrar(((chave_produto(v["link"]), v["price"]) for v in vistos), quando=hoje, db=db)
    return resultados


def pontuar_e_ordenar(resultados: list[dict], vistos: list[dict], hoje: date | None = None, db=None) -> list[dict]:
    """Pontua e ordena pela nota. Se algo falhar, a coleta nao se perde: volta para
    a ordem por desconto, sem nota."""
    try:
        pontuar(resultados, vistos, hoje=hoje, db=db)
        ordenar_por_score(resultados)
    except Exception as e:  # noqa: BLE001
        print(f"[Deal Score] falhou ({e}); mantendo ordem por desconto.")
        resultados.sort(key=lambda o: o.get("discount", 0), reverse=True)
    return resultados


def ordenar_por_score(resultados: list[dict]) -> list[dict]:
    """Melhor Deal Score primeiro; sem nota vai para o fim; desempate pelo desconto."""
    resultados.sort(key=lambda o: (o.get("deal_score") is not None, o.get("deal_score") or 0, o.get("discount", 0)),
                    reverse=True)
    return resultados


def linha_terminal(oferta: dict) -> str:
    """Linha para o terminal dos scrapers."""
    s = oferta.get("deal_score")
    txt = "sem nota" if s is None else f"{s}/100"
    conf = oferta.get("deal_confianca", "nenhuma")
    flags = oferta.get("deal_flags") or []
    extra = f" [{', '.join(flags)}]" if flags else ""
    return f"   DEAL SCORE: {txt} (confiança {conf}){extra}"
