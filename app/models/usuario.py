from datetime import date
from pydantic import BaseModel, EmailStr, Field, field_validator


class UsuarioRegistro(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    correo: EmailStr
    password: str = Field(min_length=8, max_length=64)
    fecha_nacimiento: date

    @field_validator("fecha_nacimiento")
    @classmethod
    def no_futura(cls, v: date):
        if v >= date.today():
            raise ValueError("La fecha de nacimiento debe ser anterior a hoy")
        return v