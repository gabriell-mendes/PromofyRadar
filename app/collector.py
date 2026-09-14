"""OBSOLETO — substituído por app/sources/ (ver docs/decisao-fonte-de-dados.md).

Este arquivo só existe porque a sessão que fez essa refatoração não
conseguiu apagar arquivos na sua pasta local (device_bash indisponível
neste ambiente). Pode apagar com segurança:

    Remove-Item app\\collector.py

Nada no projeto importa mais deste módulo — a lógica que tinha
`buscar_produtos_raw`/`normalizar` do Mercado Livre agora está em
`app/sources/mercadolivre.py` (implementando a interface `OfferSource` de
`app/sources/base.py`), e a fonte usada por padrão pelo MVP é
`app/sources/shopee.py`.
"""
