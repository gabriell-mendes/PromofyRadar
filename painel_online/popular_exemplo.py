"""Enche o banco LOCAL de teste do painel online com ofertas de exemplo (todas inventadas).

    .\\.venv\\Scripts\\python.exe -m painel_online.popular_exemplo [NOME_DO_USUARIO]

O usuário precisa existir (criar-admin). Rodar de novo atualiza as mesmas ofertas, não duplica.
Recusa rodar no banco do servidor (/var/lib/painel).
"""

import sys

from .db import agora_iso, caminho_db, conectar, criar_tabelas
from .ingest import ingerir

# (título, categoria, preço, preço original, Deal Score, confiança)
EXEMPLOS = [
    ("SSD NVMe Kingston NV3 1TB M.2 PCIe 4.0", "Informática", 389.90, 549.90, 82, "alta"),
    ("Notebook Acer Aspire 5 Core i5 8GB 512GB SSD 15.6 Full HD", "Informática", 2799.00, 3499.00, 74, "média"),
    ("Monitor Gamer LG UltraGear 24 144Hz IPS 1ms", "Informática", 899.00, 1299.00, 68, "alta"),
    ("Mouse Gamer Logitech G203 RGB 8000 DPI", "Informática", 89.90, 149.90, 55, "média"),
    ("Smartphone Samsung Galaxy A15 128GB 4GB RAM", "Celulares e Telefones", 949.00, 1299.00, 71, "alta"),
    ("Smartphone Motorola Moto G24 128GB 4GB RAM", "Celulares e Telefones", 719.00, 899.00, 49, "média"),
    ("Fone Bluetooth JBL Tune 520BT Sem Fio", "Eletrônicos, Áudio e Vídeo", 169.00, 299.00, 77, "alta"),
    ("Caixa de Som Bluetooth Xiaomi Mi Portable 16W", "Eletrônicos, Áudio e Vídeo", 219.00, 329.00, 63, "média"),
    ("Smart TV 50 Polegadas 4K UHD LED Samsung", "Televisores", 2099.00, 2999.00, 79, "alta"),
    ("Smart TV 43 Polegadas Full HD LG ThinQ", "Televisores", 1599.00, 1899.00, 42, "baixa"),
    ("Console PlayStation 5 Slim Edição Digital 1TB", "Games", 3499.00, 3899.00, 58, "média"),
    ("Controle Xbox Wireless Carbon Black", "Games", 299.00, 449.00, 66, "alta"),
    ("Fritadeira Air Fryer Mondial 4L Preta", "Eletrodomésticos", 259.00, 399.00, 72, "alta"),
    ("Aspirador de Pó Robô Xiaomi Robot Vacuum E5", "Eletrodomésticos", 899.00, 1299.00, 61, "média"),
    ("Cadeira de Escritório Ergonômica com Apoio Lombar", "Casa e Móveis", 529.00, 799.00, 52, "média"),
    ("Jogo de Panelas Antiaderente 5 Peças Tramontina", "Casa e Móveis", 189.00, 299.00, 47, "baixa"),
    ("Kit Halteres Ajustáveis 20kg com Barra", "Esportes e Fitness", 229.00, 349.00, 56, "média"),
    ("Furadeira de Impacto Bosch 550W com Maleta", "Ferramentas", 249.00, 329.00, 38, "baixa"),
    ("Ração Premier Cães Adultos 15kg", "Pet Shop", 189.90, 239.90, None, None),
    ("Câmera de Segurança Wi-Fi Full HD Giratória", "Câmeras e Acessórios", 129.90, 219.90, None, None),
    ("Mochila Impermeável para Notebook até 15.6", "Outros", 99.90, 99.90, None, None),
]


def montar(i: int, item: tuple) -> dict:
    titulo, categoria, preco, original, score, confianca = item
    desconto = round((1 - preco / original) * 100) if original > preco else None
    oferta = {
        "loja": "mercadolivre",
        "url": f"https://produto.mercadolivre.com.br/MLB-{9000000 + i}-exemplo-_JM",
        "titulo": titulo,
        "preco": preco,
        "preco_original": original if original > preco else None,
        "desconto": desconto,
        "parcelamento": f"em 10x R$ {preco / 10:.2f}".replace(".", ","),
        "categoria": categoria,
    }
    if score is not None:
        oferta["deal_score"] = score
        oferta["deal_confianca"] = confianca
    return oferta


def main(argv: list[str]) -> int:
    nome = argv[1].strip() if len(argv) > 1 else "teste"
    db = caminho_db()
    if str(db).startswith("/var/lib"):
        print("Recusado: este é o banco do servidor. Este script é só para o banco de teste local.")
        return 1
    con = conectar(db)
    criar_tabelas(con)
    try:
        usuario = con.execute("SELECT id FROM usuarios WHERE nome = ?", (nome,)).fetchone()
        if usuario is None:
            print(f"Usuário '{nome}' não existe em {db}. Crie com: python -m painel_online.cli criar-admin {nome}")
            return 1
        resumo = ingerir(con, usuario["id"], [montar(i, item) for i, item in enumerate(EXEMPLOS)])
        # Descarta duas para a aba Descartadas ter o que mostrar.
        agora = agora_iso()
        for titulo in ("Mochila Impermeável para Notebook até 15.6", "Furadeira de Impacto Bosch 550W com Maleta"):
            con.execute(
                "INSERT OR IGNORE INTO descartados (oferta_id, descartado_em, descartado_por) "
                "SELECT id, ?, ? FROM ofertas WHERE titulo = ?",
                (agora, usuario["id"], titulo),
            )
        print(f"Banco: {db}")
        print(f"Ofertas: {resumo['criadas']} criadas, {resumo['atualizadas']} atualizadas, {len(resumo['detalhes_ignoradas'])} ignoradas.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
