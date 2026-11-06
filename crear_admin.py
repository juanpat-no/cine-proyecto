from datetime import datetime
from app.database import db
from app.seguridad import hashear

CORREO = "admin@cine.com"
PASSWORD = "Admin12345"

db["usuarios"].create_index("correo", unique=True)
db["usuarios"].update_one(
    {"correo": CORREO},
    {"$set": {
        "nombre": "Administrador",
        "correo": CORREO,
        "password_hash": hashear(PASSWORD),
        "rol": "admin",
        "fecha_nacimiento": datetime(1990, 1, 1),
        "creado": datetime.now(),
    }},
    upsert=True,
)
print("Admin listo:", CORREO)