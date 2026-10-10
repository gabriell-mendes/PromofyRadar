from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class OfertaIn(BaseModel):
    """Oferta enviada por um PC ao painel online (contrato da Etapa 1).

    Fora de proposito: id_produto (derivado de url por quem recebe) e
    enviado_por (vem do token de autenticacao, Etapa 3).
    """

    loja: str
    url: str
    titulo: str
    preco: float = Field(gt=0)
    preco_original: float | None = None
    desconto: float | None = None
    parcelamento: str | None = None
    imagem: str | None = None
    categoria: str | None = None
    deal_score: int | None = None
    deal_confianca: str | None = None
    deal_motivos: list[str] = Field(default_factory=list)
    deal_flags: list[str] = Field(default_factory=list)
    coletado_em: datetime | None = None

    @field_validator("url", "imagem")
    @classmethod
    def so_http(cls, v: str | None) -> str | None:
        # O painel mostra esses valores como link e imagem. Recusar "javascript:" e
        # afins aqui fecha a porta para XSS vindo de dados enviados.
        if v is not None and not v.lower().startswith(("http://", "https://")):
            raise ValueError("deve começar com http:// ou https://")
        return v
