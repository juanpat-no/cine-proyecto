import re
from datetime import datetime
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import db
from app.models.sala import SalaCrear, SalaActualizar
from app.seguridad import requerir_admin

router = APIRouter(prefix="/salas", tags=["Salas"])
coleccion = db["salas"]


def a_object_id(id: str) -> ObjectId:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="ID inválido")
    return ObjectId(id)


def serializar(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def generar_asientos(filas: int, columnas: int) -> list:
    return [
        {"codigo": f"{chr(65 + f)}{c}", "fila": chr(65 + f), "numero": c}
        for f in range(filas)
        for c in range(1, columnas + 1)
    ]


@router.post("/", status_code=201, dependencies=[Depends(requerir_admin)])
def crear_sala(datos: SalaCrear):
    existe = coleccion.find_one(
        {"nombre": {"$regex": f"^{re.escape(datos.nombre)}$", "$options": "i"}}
    )
    if existe:
        raise HTTPException(status_code=409, detail="Ya existe una sala con ese nombre")
    asientos = generar_asientos(datos.filas, datos.columnas)
    documento = {
        "nombre": datos.nombre,
        "tipo": datos.tipo,
        "filas": datos.filas,
        "columnas": datos.columnas,
        "capacidad": len(asientos),
        "asientos": asientos,
    }
    resultado = coleccion.insert_one(documento)
    documento["_id"] = resultado.inserted_id
    return serializar(documento)


@router.get("/")
def listar_salas(tipo: Optional[str] = Query(None)):
    filtro = {"tipo": tipo} if tipo else {}
    return [serializar(d) for d in coleccion.find(filtro, {"asientos": 0}).sort("nombre", 1)]


@router.get("/{id}")
def obtener_sala(id: str):
    doc = coleccion.find_one({"_id": a_object_id(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return serializar(doc)


@router.put("/{id}", dependencies=[Depends(requerir_admin)])
def actualizar_sala(id: str, datos: SalaActualizar):
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(status_code=400, detail="No se enviaron cambios")
    if "nombre" in cambios:
        repetida = coleccion.find_one(
            {
                "_id": {"$ne": a_object_id(id)},
                "nombre": {"$regex": f"^{re.escape(cambios['nombre'])}$", "$options": "i"},
            }
        )
        if repetida:
            raise HTTPException(status_code=409, detail="Ya existe una sala con ese nombre")
    resultado = coleccion.update_one({"_id": a_object_id(id)}, {"$set": cambios})
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return serializar(coleccion.find_one({"_id": a_object_id(id)}))


@router.delete("/{id}", dependencies=[Depends(requerir_admin)])
def eliminar_sala(id: str):
    oid = a_object_id(id)
    futuras = db["funciones"].find_one({"sala_id": oid, "inicio": {"$gte": datetime.now()}})
    if futuras:
        raise HTTPException(
            status_code=409, detail="No se puede eliminar: la sala tiene funciones programadas"
        )
    resultado = coleccion.delete_one({"_id": oid})
    if resultado.deleted_count == 0:
        raise