import os
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.database import db

load_dotenv()
SECRET = os.getenv("JWT_SECRET")
ALGORITMO = "HS256"
HORAS_TOKEN = 8

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hashear(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar(password: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(password.encode(), hash_guardado.encode())


def crear_token(usuario: dict) -> str:
    datos = {
        "sub": str(usuario["_id"]),
        "rol": usuario["rol"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=HORAS_TOKEN),
    }
    return jwt.encode(datos, SECRET, algorithm=ALGORITMO)


def usuario_actual(token: str = Depends(oauth2)) -> dict:
    try:
        datos = jwt.decode(token, SECRET, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o vencido")
    usuario = db["usuarios"].find_one({"_id": ObjectId(datos["sub"])})
    if not usuario:
        raise HTTPException(status_code=401, detail="El usuario ya no existe")
    return usuario


def requerir_admin(usuario: dict = Depends(usuario_actual)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede hacer esto")
    return usuario