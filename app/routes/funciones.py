from datetime import date, datetime, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.models.funcion import FuncionCrear, FuncionActualizar
from app.seguridad import requerir_admin

router = APIRouter(prefix="/funciones", tags=["Funciones"])
coleccion = db["funciones"]
MINUTOS_ASEO = 15


def a_object_id(id: str) -> ObjectId:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="ID inválido")
    return ObjectId(id)


def serializar(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    for campo in ("pelicula_id", "sala_id"):
        if isinstance(doc.get(campo), ObjectId):
            doc[campo] = str(doc[campo])
    return doc


@router.post("/", status_code=201, dependencies=[Depends(requerir_admin)])
def crear_funcion(datos: FuncionCrear):
    pelicula = db["peliculas"].find_one({"_id": a_object_id(datos.pelicula_id)})
    if not pelicula:
        raise HTTPException(status_code=404, detail="La película no existe")
    if pelicula["estado"] == "retirada":
        raise HTTPException(status_code=409, detail="No se puede programar una película retirada")

    sala = db["salas"].find_one({"_id": a_object_id(datos.sala_id)}, {"asientos": 0})
    if not sala:
        raise HTTPException(status_code=404, detail="La sala no existe")

    inicio = datos.inicio.replace(tzinfo=None)
    if inicio <= datetime.now():
        raise HTTPException(status_code=400, detail="La función debe programarse en el futuro")

    fin = inicio + timedelta(minutes=pelicula["duracion_min"] + MINUTOS_ASEO)

    cruce = coleccion.find_one(
        {"sala_id": sala["_id"], "inicio": {"$lt": fin}, "fin": {"$gt": inicio}}
    )
    if cruce:
        raise HTTPException(
            status_code=409,
            detail=f"La sala ya tiene una función entre {cruce['inicio']:%H:%M} y {cruce['fin']:%H:%M}",
        )

    documento = {
        "pelicula_id": pelicula["_id"],
        "sala_id": sala["_id"],
        "inicio": inicio,
        "fin": fin,
        "precio": datos.precio,
        "asientos_ocupados": [],
    }
    resultado = coleccion.insert_one(documento)
    documento["_id"] = resultado.inserted_id
    return serializar(documento)


@router.get("/")
def listar_funciones(
    pelicula_id: Optional[str] = None,
    sala_id: Optional[str] = None,
    fecha: Optional[date] = None,
):
    filtro = {}
    if pelicula_id:
        filtro["pelicula_id"] = a_object_id(pelicula_id)
    if sala_id:
        filtro["sala_id"] = a_object_id(sala_id)
    if fecha:
        desde = datetime.combine(fecha, datetime.min.time())
        filtro["inicio"] = {"$gte": desde, "$lt": desde + timedelta(days=1)}

    pipeline = [
        {"$match": filtro},
        {"$lookup": {"from": "peliculas", "localField": "pelicula_id",
                     "foreignField": "_id", "as": "pelicula"}},
        {"$lookup": {"from": "salas", "localField": "sala_id",
                     "foreignField": "_id", "as": "sala"}},
        {"$unwind": "$pelicula"},
        {"$unwind": "$sala"},
        {"$project": {
            "inicio": 1,
            "fin": 1,
            "precio": 1,
            "pelicula": "$pelicula.titulo",
            "clasificacion": "$pelicula.clasificacion",
            "sala": "$sala.nombre",
            "tipo_sala": "$sala.tipo",
            "capacidad": "$sala.capacidad",
            "ocupados": {"$size": "$asientos_ocupados"},
        }},
        {"$sort": {"inicio": 1}},
    ]
    return [serializar(d) for d in coleccion.aggregate(pipeline)]


@router.get("/{id}")
def obtener_funcion(id: str):
    doc = coleccion.find_one({"_id": a_object_id(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Función no encontrada")
    return serializar(doc)


@router.put("/{id}", dependencies=[Depends(requerir_admin)])
def actualizar_funcion(id: str, datos: FuncionActualizar):
    resultado = coleccion.update_one(
        {"_id": a_object_id(id)}, {"$set": {"precio": datos.precio}}
    )
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Función no encontrada")
    return serializar(coleccion.find_one({"_id": a_object_id(id)}))


@router.delete("/{id}", dependencies=[Depends(requerir_admin)])
def eliminar_funcion(id: str):
    doc = coleccion.find_one({"_id": a_object_id(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Función no encontrada")
    if doc["asientos_ocupados"]:
        raise HTTPException(status_code=409, detail="No se puede eliminar: ya hay boletas vendidas")
    coleccion.delete_one({"_id": doc["_id"]})
    return {"mensaje": "Función eliminada"}