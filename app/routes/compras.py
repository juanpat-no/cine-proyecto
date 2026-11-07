from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.models.compra import CompraCrear
from app.seguridad import usuario_actual

router = APIRouter(prefix="/compras", tags=["Compras"])
coleccion = db["compras"]
coleccion.create_index("usuario_id")

EDAD_MINIMA = {"TP": 0, "+7": 7, "+12": 12, "+15": 15, "+18": 18}
HORAS_CANCELACION = 2


def a_object_id(id: str) -> ObjectId:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="ID inválido")
    return ObjectId(id)


def serializar(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    for campo in ("usuario_id", "funcion_id"):
        if isinstance(doc.get(campo), ObjectId):
            doc[campo] = str(doc[campo])
    return doc


def calcular_edad(nacimiento: datetime, hoy: datetime) -> int:
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


@router.post("/", status_code=201)
def crear_compra(datos: CompraCrear, usuario: dict = Depends(usuario_actual)):
    ahora = datetime.now()

    funcion = db["funciones"].find_one({"_id": a_object_id(datos.funcion_id)})
    if not funcion:
        raise HTTPException(status_code=404, detail="La función no existe")
    if funcion["inicio"] <= ahora:
        raise HTTPException(status_code=409, detail="La función ya inició, no se pueden vender boletas")

    pelicula = db["peliculas"].find_one({"_id": funcion["pelicula_id"]})
    edad = calcular_edad(usuario["fecha_nacimiento"], ahora)
    minima = EDAD_MINIMA[pelicula["clasificacion"]]
    if edad < minima:
        raise HTTPException(
            status_code=403,
            detail=f"Esta película es para mayores de {minima} años",
        )

    sala = db["salas"].find_one({"_id": funcion["sala_id"]}, {"asientos.codigo": 1})
    validos = {a["codigo"] for a in sala["asientos"]}
    invalidos = [a for a in datos.asientos if a not in validos]
    if invalidos:
        raise HTTPException(status_code=400, detail=f"Asientos que no existen en la sala: {invalidos}")

    reserva = db["funciones"].update_one(
        {"_id": funcion["_id"], "asientos_ocupados": {"$nin": datos.asientos}},
        {"$push": {"asientos_ocupados": {"$each": datos.asientos}}},
    )
    if reserva.modified_count == 0:
        raise HTTPException(status_code=409, detail="Alguno de los asientos ya fue vendido")

    documento = {
        "usuario_id": usuario["_id"],
        "funcion_id": funcion["_id"],
        "asientos": datos.asientos,
        "precio_unitario": funcion["precio"],
        "total": funcion["precio"] * len(datos.asientos),
        "estado": "activa",
        "creada": ahora,
    }
    try:
        resultado = coleccion.insert_one(documento)
    except Exception:
        db["funciones"].update_one(
            {"_id": funcion["_id"]},
            {"$pull": {"asientos_ocupados": {"$in": datos.asientos}}},
        )
        raise HTTPException(status_code=500, detail="No se pudo registrar la compra")
    documento["_id"] = resultado.inserted_id
    return serializar(documento)


@router.get("/mias")
def mis_compras(usuario: dict = Depends(usuario_actual)):
    pipeline = [
        {"$match": {"usuario_id": usuario["_id"]}},
        {"$lookup": {"from": "funciones", "localField": "funcion_id",
                     "foreignField": "_id", "as": "funcion"}},
        {"$unwind": "$funcion"},
        {"$lookup": {"from": "peliculas", "localField": "funcion.pelicula_id",
                     "foreignField": "_id", "as": "pelicula"}},
        {"$lookup": {"from": "salas", "localField": "funcion.sala_id",
                     "foreignField": "_id", "as": "sala"}},
        {"$unwind": "$pelicula"},
        {"$unwind": "$sala"},
        {"$project": {
            "asientos": 1,
            "total": 1,
            "estado": 1,
            "creada": 1,
            "pelicula": "$pelicula.titulo",
            "sala": "$sala.nombre",
            "inicio": "$funcion.inicio",
        }},
        {"$sort": {"creada": -1}},
    ]
    return [serializar(d) for d in coleccion.aggregate(pipeline)]


@router.post("/{id}/cancelar")
def cancelar_compra(id: str, usuario: dict = Depends(usuario_actual)):
    compra = coleccion.find_one({"_id": a_object_id(id)})
    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if compra["usuario_id"] != usuario["_id"] and usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Esta compra no es tuya")
    if compra["estado"] != "activa":
        raise HTTPException(status_code=409, detail="La compra ya estaba cancelada")

    funcion = db["funciones"].find_one({"_id": compra["funcion_id"]})
    limite = funcion["inicio"] - timedelta(hours=HORAS_CANCELACION)
    if datetime.now() > limite:
        raise HTTPException(
            status_code=409,
            detail=f"Solo se puede cancelar hasta {HORAS_CANCELACION} horas antes de la función",
        )

    cambio = coleccion.update_one(
        {"_id": compra["_id"], "estado": "activa"},
        {"$set": {"estado": "cancelada", "cancelada_en": datetime.now()}},
    )
    if cambio.modified_count == 0:
        raise HTTPException(status_code=409, detail="La compra ya estaba cancelada")

    db["funciones"].update_one(
        {"_id": funcion["_id"]},
        {"$pull": {"asientos_ocupados": {"$in": compra["asientos"]}}},
    )
    return {"mensaje": "Compra cancelada y asientos liberados"}