from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError
from app.database import db
from app.models.usuario import UsuarioRegistro
from app.seguridad import hashear, verificar, crear_token, usuario_actual

router = APIRouter(prefix="/auth", tags=["Autenticación"])
coleccion = db["usuarios"]
coleccion.create_index("correo", unique=True)


def publico(u: dict) -> dict:
    return {
        "id": str(u["_id"]),
        "nombre": u["nombre"],
        "correo": u["correo"],
        "rol": u["rol"],
        "fecha_nacimiento": u["fecha_nacimiento"].date().isoformat(),
    }


@router.post("/registro", status_code=201)
def registrar(datos: UsuarioRegistro):
    documento = {
        "nombre": datos.nombre,
        "correo": datos.correo.lower(),
        "password_hash": hashear(datos.password),
        "rol": "cliente",
        "fecha_nacimiento": datetime.combine(datos.fecha_nacimiento, datetime.min.time()),
        "creado": datetime.now(),
    }
    try:
        resultado = coleccion.insert_one(documento)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")
    documento["_id"] = resultado.inserted_id
    return publico(documento)


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    usuario = coleccion.find_one({"correo": form.username.lower()})
    if not usuario or not verificar(form.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    return {"access_token": crear_token(usuario), "token_type": "bearer", "usuario": publico(usuario)}


@router.get("/yo")
def perfil(usuario: dict = Depends(usuario_actual)):
    return publico(usuario)