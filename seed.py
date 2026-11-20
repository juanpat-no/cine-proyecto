import random
import sys
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.database import db
from app.seguridad import hashear

random.seed(42)

EDAD_MINIMA = {"TP": 0, "+7": 7, "+12": 12, "+15": 15, "+18": 18}
ASEO = 15
DIAS_ATRAS = 21
DIAS_ADELANTE = 7

PELICULAS = [
    ("Interestelar", "Ciencia ficción", 169, "+12", "en_cartelera",
     "Un grupo de astronautas cruza un agujero de gusano en busca de un nuevo hogar para la humanidad."),
    ("Parásitos", "Drama", 132, "+15", "en_cartelera",
     "Una familia pobre se infiltra poco a poco en la vida de una familia adinerada."),
    ("Coco", "Animación", 105, "TP", "en_cartelera",
     "Un niño sueña con ser músico y termina en la Tierra de los Muertos."),
    ("Mad Max: Furia en el camino", "Acción", 120, "+15", "en_cartelera",
     "Una huida a toda velocidad por el desierto contra un tirano y su ejército."),
    ("Pulp Fiction", "Crimen", 154, "+18", "en_cartelera",
     "Historias entrelazadas de criminales en Los Ángeles."),
    ("Toy Story", "Animación", 81, "TP", "en_cartelera",
     "Los juguetes de un niño cobran vida cuando nadie los ve."),
    ("Origen", "Ciencia ficción", 148, "+12", "en_cartelera",
     "Un ladrón entra en los sueños de otros para robar sus secretos."),
    ("La La Land", "Musical", 128, "+7", "en_cartelera",
     "Una actriz y un pianista persiguen sus sueños en Los Ángeles."),
    ("Spider-Man: Un nuevo universo", "Animación", 117, "+7", "en_cartelera",
     "Un adolescente de Brooklyn descubre que hay muchos Spider-Man en el multiverso."),
    ("Gladiador", "Acción", 155, "+15", "proximamente",
     "Un general romano traicionado busca venganza en la arena."),
]

SALAS = [
    ("Sala 1", "2D", 8, 10),
    ("Sala 2", "2D", 8, 12),
    ("Sala 3", "3D", 10, 12),
    ("Sala VIP", "VIP", 5, 8),
]
PRECIO_BASE = {"2D": 14000, "3D": 18000, "VIP": 28000}

CLIENTES = [
    ("Laura Gómez", "laura.gomez@correo.com", None),
    ("Carlos Ramírez", "carlos.ramirez@correo.com", None),
    ("Valentina Torres", "valentina.torres@correo.com", None),
    ("Andrés Molina", "andres.molina@correo.com", None),
    ("Camila Herrera", "camila.herrera@correo.com", None),
    ("Sebastián Ríos", "sebastian.rios@correo.com", None),
    ("Daniela Vargas", "daniela.vargas@correo.com", None),
    ("Mateo Castaño", "mateo.castano@correo.com", None),
    ("Juliana Ospina", "juliana.ospina@correo.com", None),
    ("Felipe Duque", "felipe.duque@correo.com", None),
    ("Sofía Mejía", "sofia.mejia@correo.com", 2014),
    ("Tomás Restrepo", "tomas.restrepo@correo.com", 2013),
]
PASSWORD_CLIENTES = "Cliente123"


def edad(nacimiento, hoy):
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def generar_asientos(filas, columnas):
    return [
        {"codigo": f"{chr(65 + f)}{c}", "fila": chr(65 + f), "numero": c}
        for f in range(filas)
        for c in range(1, columnas + 1)
    ]


def tasa_ocupacion(inicio, tipo, ahora):
    base = 0.35
    if inicio.weekday() >= 4:
        base += 0.25
    if inicio.hour >= 18:
        base += 0.15
    if tipo == "VIP":
        base -= 0.10
    tasa = max(0.05, min(0.95, random.gauss(base, 0.15)))
    if inicio > ahora:
        tasa *= random.uniform(0.0, 0.5)
    return tasa


PROB_RESENA = 0.7      # fracción de parejas cliente-película que dejan reseña
PROB_COMENTARIO = 0.7  # fracción de reseñas que llevan texto
COMENTARIOS = {
    5: [
        "Una experiencia increíble, el sonido y la sala ayudaron muchísimo.",
        "De lo mejor que he visto este año. La recomiendo sin dudarlo.",
        "Final espectacular, salí del cine sin palabras.",
        "Actuaciones brillantes y una historia que te atrapa de principio a fin.",
    ],
    4: [
        "Muy buena, con un par de momentos lentos pero vale la pena.",
        "Entretenida de principio a fin. Volvería a verla.",
        "Buena película, la fotografía es hermosa.",
    ],
    3: [
        "Cumple, pero esperaba un poco más.",
        "Está bien para pasar el rato, aunque no es memorable.",
        "Tiene buenas ideas, pero el ritmo decae a la mitad.",
    ],
    2: [
        "Me costó engancharme con la historia.",
        "Prometía mucho y se quedó corta.",
    ],
    1: [
        "No me gustó, el guion no se sostiene.",
    ],
}


def sembrar_resenas(ahora):
    """Crea reseñas de ejemplo para cada pareja cliente-película con una compra activa de una
    función ya iniciada (la misma regla de la API). Solo agrega: el índice único impide duplicados."""
    rnd = random.Random(42)  # semilla propia: no altera el resto de datos y es repetible
    resenas = db["resenas"]
    resenas.create_index([("usuario_id", 1), ("pelicula_id", 1)], unique=True)
    resenas.create_index([("pelicula_id", 1), ("creada", -1)])

    clientes = {u["_id"]: u for u in db["usuarios"].find({"rol": "cliente"})}
    pipeline = [
        {"$match": {"estado": "activa"}},
        {"$lookup": {"from": "funciones", "localField": "funcion_id",
                     "foreignField": "_id", "as": "funcion"}},
        {"$unwind": "$funcion"},
        {"$match": {"funcion.inicio": {"$lt": ahora}}},
        {"$group": {"_id": {"u": "$usuario_id", "p": "$funcion.pelicula_id"},
                    "inicio": {"$min": "$funcion.inicio"}}},
    ]
    # El orden de un aggregate no está garantizado: se ordena para que el resultado sea repetible.
    parejas = sorted(
        ((d["_id"]["u"], d["_id"]["p"], d["inicio"]) for d in db["compras"].aggregate(pipeline)),
        key=lambda t: (str(t[0]), str(t[1])),
    )
    if not parejas:
        print("No hay compras activas de funciones ya iniciadas: no se crearon reseñas.")
        return

    medias = {}  # cada película tiene una calidad base distinta, así los promedios varían
    creadas = repetidas = 0
    for usuario_id, pelicula_id, inicio in parejas:
        usuario = clientes.get(usuario_id)
        if not usuario or rnd.random() > PROB_RESENA:
            continue
        if pelicula_id not in medias:
            medias[pelicula_id] = rnd.uniform(3.0, 4.7)
        nota = max(1, min(5, round(rnd.gauss(medias[pelicula_id], 0.9))))
        comentario = rnd.choice(COMENTARIOS[nota]) if rnd.random() < PROB_COMENTARIO else ""
        try:
            resenas.insert_one({
                "pelicula_id": pelicula_id,
                "usuario_id": usuario_id,
                "nombre_usuario": usuario["nombre"],
                "calificacion": nota,
                "comentario": comentario,
                "creada": min(ahora, inicio + timedelta(hours=rnd.randint(3, 72))),
                "editada": None,
            })
            creadas += 1
        except DuplicateKeyError:
            repetidas += 1
    print(f"Reseñas creadas: {creadas} | ya existían: {repetidas} | total en '{db.name}': {resenas.count_documents({})}")


def main():
    ahora = datetime.now()

    if "--solo-resenas" in sys.argv:
        # Solo agrega reseñas, no borra nada: es la única forma de usar este script en 'cine'.
        print(f"Base de datos: {db.name} (solo se agregan reseñas)")
        if db.name == "cine" and input("Es la base de PRODUCCIÓN. Escribe 'cine' para continuar: ").strip() != "cine":
            print("Cancelado")
            return
        sembrar_resenas(ahora)
        return

    if db.name == "cine":
        sys.exit("Este script borra datos y no se puede ejecutar contra la base de producción 'cine'. "
                 "Para agregar solo reseñas usa: python seed.py --solo-resenas")

    if input(f"Base de datos: {db.name}. Esto borra peliculas, salas, funciones, compras, resenas y clientes. Escribe SI para continuar: ") != "SI":
        print("Cancelado")
        return

    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

    for nombre in ("peliculas", "salas", "funciones", "compras", "resenas"):
        db[nombre].delete_many({})
    db["usuarios"].delete_many({"rol": "cliente"})

    db["usuarios"].create_index("correo", unique=True)
    db["funciones"].create_index([("sala_id", 1), ("inicio", 1)])
    db["funciones"].create_index("pelicula_id")
    db["compras"].create_index("usuario_id")
    db["compras"].create_index("funcion_id")
    db["compras"].create_index("creada")

    db["usuarios"].update_one(
        {"correo": "admin@cine.com"},
        {"$set": {
            "nombre": "Administrador", "correo": "admin@cine.com",
            "password_hash": hashear("Admin12345"), "rol": "admin",
            "fecha_nacimiento": datetime(1990, 1, 1), "creado": ahora,
        }},
        upsert=True,
    )

    peliculas = []
    for titulo, genero, duracion, clasif, estado, sinopsis in PELICULAS:
        peliculas.append({
            "_id": ObjectId(), "titulo": titulo, "sinopsis": sinopsis,
            "duracion_min": duracion, "genero": genero,
            "clasificacion": clasif, "estado": estado,
        })
    db["peliculas"].insert_many(peliculas)

    salas = []
    for nombre, tipo, filas, columnas in SALAS:
        asientos = generar_asientos(filas, columnas)
        salas.append({
            "_id": ObjectId(), "nombre": nombre, "tipo": tipo, "filas": filas,
            "columnas": columnas, "capacidad": len(asientos), "asientos": asientos,
        })
    db["salas"].insert_many(salas)

    clave = hashear(PASSWORD_CLIENTES)
    clientes = []
    for nombre, correo, anio in CLIENTES:
        if anio:
            nacimiento = datetime(anio, random.randint(1, 12), random.randint(1, 28))
        else:
            nacimiento = datetime(random.randint(1965, 2005), random.randint(1, 12), random.randint(1, 28))
        clientes.append({
            "_id": ObjectId(), "nombre": nombre, "correo": correo,
            "password_hash": clave, "rol": "cliente",
            "fecha_nacimiento": nacimiento, "creado": ahora - timedelta(days=random.randint(20, 60)),
        })
    db["usuarios"].insert_many(clientes)

    cartelera = [p for p in peliculas if p["estado"] == "en_cartelera"]
    peli_por_id = {p["_id"]: p for p in peliculas}
    lista_funciones = []
    lista_compras = []

    for d in range(-DIAS_ATRAS, DIAS_ADELANTE + 1):
        dia = hoy + timedelta(days=d)
        for sala in salas:
            inicio = dia + timedelta(hours=14, minutes=random.choice([0, 15, 30]))
            limite = dia + timedelta(hours=22, minutes=30)
            while inicio < limite:
                peli = random.choice(cartelera)
                fin = inicio + timedelta(minutes=peli["duracion_min"] + ASEO)
                precio = PRECIO_BASE[sala["tipo"]] + (2000 if inicio.weekday() >= 4 else 0)

                codigos = [a["codigo"] for a in sala["asientos"]]
                random.shuffle(codigos)
                vendidos = codigos[: int(len(codigos) * tasa_ocupacion(inicio, sala["tipo"], ahora))]

                funcion_id = ObjectId()
                lista_funciones.append({
                    "_id": funcion_id, "pelicula_id": peli["_id"], "sala_id": sala["_id"],
                    "inicio": inicio, "fin": fin, "precio": precio,
                    "asientos_ocupados": vendidos,
                })

                elegibles = [
                    c for c in clientes
                    if edad(c["fecha_nacimiento"], ahora) >= EDAD_MINIMA[peli["clasificacion"]]
                ]

                def nueva_compra(asientos, estado):
                    creada = min(
                        inicio - timedelta(hours=random.uniform(3, 72)),
                        ahora - timedelta(minutes=random.randint(1, 4000)),
                    )
                    compra = {
                        "usuario_id": random.choice(elegibles)["_id"],
                        "funcion_id": funcion_id,
                        "asientos": asientos,
                        "precio_unitario": precio,
                        "total": precio * len(asientos),
                        "estado": estado,
                        "creada": creada,
                    }
                    if estado == "cancelada":
                        compra["cancelada_en"] = creada + timedelta(minutes=random.randint(10, 600))
                    return compra

                i = 0
                activas = 0
                while i < len(vendidos):
                    grupo = vendidos[i: i + random.choice([1, 2, 2, 3, 4])]
                    lista_compras.append(nueva_compra(grupo, "activa"))
                    i += len(grupo)
                    activas += 1

                for _ in range(int(activas * 0.08)):
                    grupo = random.sample(codigos, random.choice([1, 2, 3]))
                    lista_compras.append(nueva_compra(grupo, "cancelada"))

                inicio = fin + timedelta(minutes=random.choice([10, 15, 20]))
                inicio += timedelta(minutes=(-inicio.minute) % 5)

    db["funciones"].insert_many(lista_funciones)
    for i in range(0, len(lista_compras), 1000):
        db["compras"].insert_many(lista_compras[i: i + 1000])

    print(f"Peliculas: {len(peliculas)} | Salas: {len(salas)} | Clientes: {len(clientes)}")
    print(f"Funciones: {len(lista_funciones)} | Compras: {len(lista_compras)}")
    print("Admin: admin@cine.com / Admin12345")
    print(f"Clientes demo: laura.gomez@correo.com / {PASSWORD_CLIENTES}")

    sembrar_resenas(ahora)


if __name__ == "__main__":
    main()