from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from app.database import db
from app.routes import peliculas, salas, funciones

app = FastAPI(title="Cine API", docs_url=None)
app.include_router(peliculas.router)
app.include_router(salas.router)
app.include_router(funciones.router)

ESTILO_OSCURO = """
<style>
  body { background: #1b1b1f; }
  .swagger-ui { filter: invert(90%) hue-rotate(180deg); }
  .swagger-ui .microlight { filter: invert(100%) hue-rotate(180deg); }
</style>
"""


@app.get("/docs", include_in_schema=False)
def docs_oscuro():
    pagina = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Cine API - Documentación",
        swagger_ui_parameters={
            "docExpansion": "none",
            "displayRequestDuration": True,
            "persistAuthorization": True,
            "filter": True,
        },
    )
    html = pagina.body.decode().replace("</head>", ESTILO_OSCURO + "</head>")
    return HTMLResponse(html)


@app.get("/")
def inicio():
    return {"mensaje": "API del cine funcionando"}


@app.get("/salud")
def salud():
    db.command("ping")
    return {"base_de_datos": "conectada"}