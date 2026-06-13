from fastapi import FastAPI
from fastapi.responses import FileResponse
import os
from scraper import main  # tu función principal

app = FastAPI()

@app.get("/")
def home():
    return {"status": "API funcionando"}


@app.get("/catalog")
def run_catalog():
    try:
        # Ejecuta tu scraper
        main()

        file_path = "Catalogo_2026.html"

        if not os.path.exists(file_path):
            return {"error": "No se generó el HTML"}

        # Devuelve el HTML directo
        return FileResponse(file_path, media_type="text/html")

    except Exception as e:
        return {"error": str(e)}
