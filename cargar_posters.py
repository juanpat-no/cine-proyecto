import os
import requests
from dotenv import load_dotenv
from app.database import db

load_dotenv()
CLAVE = os.getenv("TMDB_API_KEY")
if not CLAVE:
    raise SystemExit("Falta TMDB_API_KEY en el .env")

BASE_IMG = "https://image.tmdb.org/t/p/w500"

for pelicula in db["peliculas"].find():
    titulo = pelicula["titulo"]
    r = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={"api_key": CLAVE, "query": titulo, "language": "es-ES"},
        timeout=15,
    )
    r.raise_for_status()
    con_poster = [x for x in r.json().get("results", []) if x.get("poster_path")]
    if not con_poster:
        print(f"Sin afiche: {titulo}")
        continue
    elegida = con_poster[0]
    db["peliculas"].update_one(
        {"_id": pelicula["_id"]},
        {"$set": {"poster_url": BASE_IMG + elegida["poster_path"]}},
    )
    print(f"OK: {titulo}  ->  {elegida.get('title')} ({(elegida.get('release_date') or '')[:4]})")