from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, Query
from app.database import db
from app.seguridad import requerir_admin

router = APIRouter(
    prefix="/reportes", tags=["Reportes"], dependencies=[Depends(requerir_admin)]
)
compras = db["compras"]
funciones = db["funciones"]

DIAS = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

CON_FUNCION = [
    {"$lookup": {"from": "funciones", "localField": "funcion_id",
                 "foreignField": "_id", "as": "funcion"}},
    {"$unwind": "$funcion"},
]
CON_PELICULA = CON_FUNCION + [
    {"$lookup": {"from": "peliculas", "localField": "funcion.pelicula_id",
                 "foreignField": "_id", "as": "pelicula"}},
    {"$unwind": "$pelicula"},
]
FUNCION_CON_DETALLE = [
    {"$lookup": {"from": "peliculas", "localField": "pelicula_id",
                 "foreignField": "_id", "as": "pelicula"}},
    {"$lookup": {"from": "salas", "localField": "sala_id",
                 "foreignField": "_id", "as": "sala"}},
    {"$unwind": "$pelicula"},
    {"$unwind": "$sala"},
]
BOLETAS = {"$sum": {"$size": "$asientos"}}


@router.get("/resumen")
def resumen():
    por_estado = {
        d["_id"]: d
        for d in compras.aggregate([
            {"$group": {"_id": "$estado", "compras": {"$sum": 1},
                        "ingresos": {"$sum": "$total"}, "boletas": BOLETAS}}
        ])
    }
    activas = por_estado.get("activa", {"compras": 0, "ingresos": 0, "boletas": 0})
    canceladas = por_estado.get("cancelada", {"compras": 0})
    total = activas["compras"] + canceladas["compras"]
    return {
        "ingresos": activas["ingresos"],
        "boletas": activas["boletas"],
        "compras_activas": activas["compras"],
        "compras_canceladas": canceladas["compras"],
        "tasa_cancelacion_pct": round(canceladas["compras"] * 100 / total, 1) if total else 0,
        "funciones_futuras": funciones.count_documents({"inicio": {"$gte": datetime.now()}}),
        "peliculas_en_cartelera": db["peliculas"].count_documents({"estado": "en_cartelera"}),
    }


@router.get("/peliculas-top")
def peliculas_top(limite: int = Query(5, ge=1, le=20)):
    pipeline = [{"$match": {"estado": "activa"}}] + CON_PELICULA + [
        {"$group": {"_id": "$pelicula._id", "titulo": {"$first": "$pelicula.titulo"},
                    "ingresos": {"$sum": "$total"}, "boletas": BOLETAS}},
        {"$sort": {"ingresos": -1}},
        {"$limit": limite},
        {"$project": {"_id": 0, "pelicula": "$titulo", "ingresos": 1, "boletas": 1}},
    ]
    return list(compras.aggregate(pipeline))


@router.get("/ventas-por-periodo")
def ventas_por_periodo(
    agrupar: Literal["dia", "mes"] = "dia",
    dias: int = Query(30, ge=1, le=365),
):
    formato = "%Y-%m-%d" if agrupar == "dia" else "%Y-%m"
    desde = datetime.now() - timedelta(days=dias)
    pipeline = [
        {"$match": {"estado": "activa", "creada": {"$gte": desde}}},
        {"$group": {"_id": {"$dateToString": {"format": formato, "date": "$creada"}},
                    "ingresos": {"$sum": "$total"}, "boletas": BOLETAS}},
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "periodo": "$_id", "ingresos": 1, "boletas": 1}},
    ]
    return list(compras.aggregate(pipeline))


@router.get("/ingresos-por-genero")
def ingresos_por_genero():
    pipeline = [{"$match": {"estado": "activa"}}] + CON_PELICULA + [
        {"$group": {"_id": "$pelicula.genero", "ingresos": {"$sum": "$total"},
                    "boletas": BOLETAS}},
        {"$sort": {"ingresos": -1}},
        {"$project": {"_id": 0, "genero": "$_id", "ingresos": 1, "boletas": 1}},
    ]
    return list(compras.aggregate(pipeline))


@router.get("/ventas-por-dia-semana")
def ventas_por_dia_semana():
    pipeline = [{"$match": {"estado": "activa"}}] + CON_FUNCION + [
        {"$group": {"_id": {"$dayOfWeek": "$funcion.inicio"},
                    "ingresos": {"$sum": "$total"}, "boletas": BOLETAS}},
    ]
    datos = {d["_id"]: d for d in compras.aggregate(pipeline)}
    resultado = []
    for n in [2, 3, 4, 5, 6, 7, 1]:
        d = datos.get(n, {"ingresos": 0, "boletas": 0})
        resultado.append({"dia": DIAS[n - 1], "ingresos": d["ingresos"], "boletas": d["boletas"]})
    return resultado


@router.get("/ocupacion-por-sala")
def ocupacion_por_sala():
    pipeline = [
        {"$match": {"inicio": {"$lt": datetime.now()}}},
        {"$lookup": {"from": "salas", "localField": "sala_id",
                     "foreignField": "_id", "as": "sala"}},
        {"$unwind": "$sala"},
        {"$group": {"_id": "$sala.nombre", "funciones": {"$sum": 1},
                    "ocupados": {"$sum": {"$size": "$asientos_ocupados"}},
                    "capacidad_total": {"$sum": "$sala.capacidad"}}},
        {"$project": {"_id": 0, "sala": "$_id", "funciones": 1,
                      "ocupacion_pct": {"$round": [
                          {"$multiply": [{"$divide": ["$ocupados", "$capacidad_total"]}, 100]}, 1]}}},
        {"$sort": {"ocupacion_pct": -1}},
    ]
    return list(funciones.aggregate(pipeline))


@router.get("/funciones-baja-ocupacion")
def funciones_baja_ocupacion(umbral: int = Query(30, ge=1, le=100)):
    pipeline = [{"$match": {"inicio": {"$gte": datetime.now()}}}] + FUNCION_CON_DETALLE + [
        {"$project": {
            "inicio": 1,
            "pelicula": "$pelicula.titulo",
            "sala": "$sala.nombre",
            "ocupados": {"$size": "$asientos_ocupados"},
            "capacidad": "$sala.capacidad",
            "ocupacion_pct": {"$round": [
                {"$multiply": [{"$divide": [{"$size": "$asientos_ocupados"}, "$sala.capacidad"]}, 100]}, 1]},
        }},
        {"$match": {"ocupacion_pct": {"$lt": umbral}}},
        {"$sort": {"inicio": 1}},
        {"$limit": 20},
        {"$project": {"_id": 0}},
    ]
    return list(funciones.aggregate(pipeline))


@router.get("/clientes-top")
def clientes_top(limite: int = Query(10, ge=1, le=50)):
    pipeline = [
        {"$match": {"estado": "activa"}},
        {"$group": {"_id": "$usuario_id", "gasto": {"$sum": "$total"},
                    "compras": {"$sum": 1}, "boletas": BOLETAS,
                    "ticket_promedio": {"$avg": "$total"}}},
        {"$sort": {"gasto": -1}},
        {"$limit": limite},
        {"$lookup": {"from": "usuarios", "localField": "_id",
                     "foreignField": "_id", "as": "usuario"}},
        {"$unwind": "$usuario"},
        {"$project": {"_id": 0, "cliente": "$usuario.nombre", "correo": "$usuario.correo",
                      "gasto": 1, "compras": 1, "boletas": 1,
                      "ticket_promedio": {"$round": ["$ticket_promedio", 0]}}},
    ]
    return list(compras.aggregate(pipeline))