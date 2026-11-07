import re
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import db
from app.models.pelicula import PeliculaCrear, PeliculaActualizar
from app.seguridad import requerir_admin
from datetime import datetime

router = APIRouter(prefix="/peliculas", tags=["Películas"])
coleccion = db["peliculas"]


def a_object_id(id: str) -> ObjectId:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="ID inválido")
    return ObjectId(id)


def serializar(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("/", status_code=201, dependencies=[Depends(requerir_admin)])
def crear_pelicula(datos: PeliculaCrear):
    existe = coleccion.find_one(
        {"titulo": {"$regex": f"^{re.escape(datos.titulo)}$", "$options": "i"}}
    )
    if existe:
        raise HTTPException(status_code=409, detail="Ya existe una película con ese título")
    documento = datos.model_dump()
    resultado = coleccion.insert_one(documento)
    documento["_id"] = resultado.inserted_id
    return serializar(documento)


@router.get("/")
def listar_peliculas(
    q: Optional[str] = Query(None, description="Buscar por título"),
    genero: Optional[str] = None,
    estado: Optional[str] = None,
    clasificacion: Optional[str] = None,
):
    filtro = {}
    if q:
        filtro["titulo"] = {"$regex": re.escape(q), "$options": "i"}
    if genero:
        filtro["genero"] = genero
    if estado:
        filtro["estado"] = estado
    if clasificacion:
        filtro["clasificacion"] = clasificacion
    return [serializar(d) for d in coleccion.find(filtro).sort("titulo", 1)]


@router.get("/{id}")
def obtener_pelicula(id: str):
    doc = coleccion.find_one({"_id": a_object_id(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Película no encontrada")
    return serializar(doc)


@router.put("/{id}", dependencies=[Depends(requerir_admin)])
def actualizar_pelicula(id: str, datos: PeliculaActualizar):
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(status_code=400, detail="No se enviaron cambios")
    resultado = coleccion.update_one({"_id": a_object_id(id)}, {"$set": cambios})
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Película no encontrada")
    return serializar(coleccion.find_one({"_id": a_object_id(id)}))


@router.delete("/{id}", dependencies=[Depends(requerir_admin)])
def eliminar_pelicula(id: str):
    oid = a_object_id(id)
    futuras = db["funciones"].find_one({"pelicula_id": oid, "inicio": {"$gte": datetime.now()}})
    if futuras:
        raise HTTPException(
            status_code=409, detail="No se puede eliminar: la película tiene funciones programadas"
        )
    resultado = coleccion.delete_one({"_id": oid})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Película no encontrada")
    return {"mensaje": "Película eliminada"}