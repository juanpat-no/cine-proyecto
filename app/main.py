from fastapi import FastAPI
from app.database import db

app = FastAPI(title="Cine API")


@app.get("/")
def inicio():
    return {"mensaje": "API del cine funcionando"}


@app.get("/salud")
def salud():
    db.command("ping")
    return {"base_de_datos": "conectada"}