from datetime import datetime
from pydantic import BaseModel, Field


class FuncionCrear(BaseModel):
    pelicula_id: str
    sala_id: str
    inicio: datetime
    precio: int = Field(gt=0, le=200000)


class FuncionActualizar(BaseModel):
    precio: int = Field(gt=0, le=200000)