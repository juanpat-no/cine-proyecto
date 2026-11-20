from pydantic import BaseModel, Field, field_validator


class ResenaGuardar(BaseModel):
    calificacion: int = Field(ge=1, le=5)
    comentario: str = Field(default="", max_length=500)

    @field_validator("comentario")
    @classmethod
    def limpiar(cls, v: str):
        return v.strip()
