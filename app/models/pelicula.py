from typing import Literal, Optional
from pydantic import BaseModel, Field

Clasificacion = Literal["TP", "+7", "+12", "+15", "+18"]
Estado = Literal["en_cartelera", "proximamente", "retirada"]


class PeliculaCrear(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    sinopsis: str = ""
    duracion_min: int = Field(gt=0, le=400)
    genero: str = Field(min_length=1)
    clasificacion: Clasificacion
    estado: Estado = "en_cartelera"
    poster_url: Optional[str] = Field(default=None, max_length=500, pattern=r"^https?://")


class PeliculaActualizar(BaseModel):
    titulo: Optional[str] = Field(default=None, min_length=1, max_length=120)
    sinopsis: Optional[str] = None
    duracion_min: Optional[int] = Field(default=None, gt=0, le=400)
    genero: Optional[str] = None
    clasificacion: Optional[Clasificacion] = None
    estado: Optional[Estado] = None
    poster_url: Optional[str] = Field(default=None, max_length=500, pattern=r"^https?://")