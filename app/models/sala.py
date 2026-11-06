from typing import Literal, Optional
from pydantic import BaseModel, Field

TipoSala = Literal["2D", "3D", "VIP"]


class SalaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    tipo: TipoSala
    filas: int = Field(ge=1, le=26)
    columnas: int = Field(ge=1, le=30)


class SalaActualizar(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=60)
    tipo: Optional[TipoSala] = None