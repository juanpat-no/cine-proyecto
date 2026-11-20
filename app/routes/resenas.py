from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError
from app.database import db
from app.models.resena import ResenaGuardar
from app.seguridad import usuario_actual

router = APIRouter(tags=["Reseñas"])
coleccion = db["resenas"]
# Una reseña por persona y película: lo garantiza la base de datos, no solo el código.
coleccion.create_index([("usuario_id", 1), ("pelicula_id", 1)], unique=True)
coleccion.create_index([("pelicula_id", 1), ("creada", -1)])


def a_object_id(id: str) -> ObjectId:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="ID inválido")
    return ObjectId(id)


def serializar(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    for campo in ("pelicula_id", "usuario_id"):
        if isinstance(doc.get(campo), ObjectId):
            doc[campo] = str(doc[campo])
    return doc


def existe_pelicula(oid: ObjectId) -> bool:
    return db["peliculas"].count_documents({"_id": oid}, limit=1) > 0


def asistio(usuario_id: ObjectId, pelicula_oid: ObjectId) -> bool:
    """True si el usuario tiene una compra activa de una función de esa película que ya inició."""
    pipeline = [
        {"$match": {"usuario_id": usuario_id, "estado": "activa"}},
        {"$lookup": {"from": "funciones", "localField": "funcion_id",
                     "foreignField": "_id", "as": "funcion"}},
        {"$unwind": "$funcion"},
        {"$match": {"funcion.pelicula_id": pelicula_oid,
                    "funcion.inicio": {"$lt": datetime.now()}}},
        {"$limit": 1},
    ]
    return len(list(db["compras"].aggregate(pipeline))) > 0


@router.get("/resenas/promedios")
def promedios():
    """Promedio y cantidad de reseñas de todas las películas en una sola consulta."""
    pipeline = [
        {"$group": {"_id": "$pelicula_id", "promedio": {"$avg": "$calificacion"},
                    "total": {"$sum": 1}}},
    ]
    return {
        str(d["_id"]): {"promedio": round(d["promedio"], 1), "total": d["total"]}
        for d in coleccion.aggregate(pipeline)
    }


@router.get("/peliculas/{id}/resenas")
def listar_resenas(
    id: str,
    pagina: int = Query(1, ge=1),
    limite: int = Query(10, ge=1, le=50),
):
    oid = a_object_id(id)
    if not existe_pelicula(oid):
        raise HTTPException(status_code=404, detail="Película no encontrada")

    stats = next(coleccion.aggregate([
        {"$match": {"pelicula_id": oid}},
        {"$facet": {
            "resumen": [{"$group": {"_id": None, "promedio": {"$avg": "$calificacion"},
                                    "total": {"$sum": 1}}}],
            "distribucion": [{"$group": {"_id": "$calificacion", "n": {"$sum": 1}}}],
        }},
    ]))
    resumen = stats["resumen"][0] if stats["resumen"] and stats["resumen"][0]["total"] else None
    total = resumen["total"] if resumen else 0
    distribucion = {str(n): 0 for n in range(5, 0, -1)}
    for d in stats["distribucion"]:
        distribucion[str(d["_id"])] = d["n"]

    docs = (coleccion.find({"pelicula_id": oid})
            .sort("creada", DESCENDING).skip((pagina - 1) * limite).limit(limite))
    return {
        "promedio": round(resumen["promedio"], 1) if resumen else 0,
        "total": total,
        "distribucion": distribucion,
        "resenas": [serializar(d) for d in docs],
        "hay_mas": pagina * limite < total,
    }


@router.get("/peliculas/{id}/resenas/mi-estado")
def mi_estado(id: str, usuario: dict = Depends(usuario_actual)):
    oid = a_object_id(id)
    mia = coleccion.find_one({"usuario_id": usuario["_id"], "pelicula_id": oid})
    puede = usuario["rol"] == "cliente" and (mia is not None or asistio(usuario["_id"], oid))
    return {"puede_resenar": puede, "mia": serializar(mia) if mia else None}


@router.post("/peliculas/{id}/resenas", status_code=201)
def crear_resena(id: str, datos: ResenaGuardar, usuario: dict = Depends(usuario_actual)):
    oid = a_object_id(id)
    if usuario["rol"] != "cliente":
        raise HTTPException(status_code=403, detail="Solo los clientes pueden dejar reseñas")
    if not existe_pelicula(oid):
        raise HTTPException(status_code=404, detail="Película no encontrada")
    if not asistio(usuario["_id"], oid):
        raise HTTPException(
            status_code=403,
            detail="Solo puedes reseñar películas que ya viste (compra activa de una función que ya inició)",
        )
    documento = {
        "pelicula_id": oid,
        "usuario_id": usuario["_id"],
        "nombre_usuario": usuario["nombre"],
        "calificacion": datos.calificacion,
        "comentario": datos.comentario,
        "creada": datetime.now(),
        "editada": None,
    }
    try:
        resultado = coleccion.insert_one(documento)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya reseñaste esta película; edita tu reseña")
    documento["_id"] = resultado.inserted_id
    return serializar(documento)


@router.put("/resenas/{id}")
def editar_resena(id: str, datos: ResenaGuardar, usuario: dict = Depends(usuario_actual)):
    oid = a_object_id(id)
    resena = coleccion.find_one({"_id": oid})
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if resena["usuario_id"] != usuario["_id"]:
        raise HTTPException(status_code=403, detail="Solo puedes editar tu propia reseña")
    coleccion.update_one(
        {"_id": oid},
        {"$set": {"calificacion": datos.calificacion, "comentario": datos.comentario,
                  "editada": datetime.now()}},
    )
    return serializar(coleccion.find_one({"_id": oid}))


@router.delete("/resenas/{id}")
def eliminar_resena(id: str, usuario: dict = Depends(usuario_actual)):
    oid = a_object_id(id)
    resena = coleccion.find_one({"_id": oid})
    if not resena:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if resena["usuario_id"] != usuario["_id"] and usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Esta reseña no es tuya")
    coleccion.delete_one({"_id": oid})
    return {"mensaje": "Reseña eliminada"}
