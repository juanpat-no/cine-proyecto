from pydantic import BaseModel, Field, field_validator


class CompraCrear(BaseModel):
    funcion_id: str
    asientos: list[str] = Field(min_length=1, max_length=8)

    @field_validator("asientos")
    @classmethod
    def normalizar(cls, v: list[str]):
        limpios = [a.strip().upper() for a in v]
        if len(set(limpios)) != len(limpios):
            raise ValueError("Hay asientos repetidos en la solicitud")
        return limpios