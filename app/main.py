from fastapi import FastAPI
from app.database import db
from app.routes import peliculas

app = FastAPI(title="Cine API")
app.include_router(peliculas.router)


@app.get("/")
def inicio():
    return {"mensaje": "API del cine funcionando"}


@app.get("/salud")
def salud():
    db.command("ping")
    return {"base_de_datos": "conectada"}