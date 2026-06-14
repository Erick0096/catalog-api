from fastapi import FastAPI
from fastapi.responses import FileResponse
from weasyprint import HTML
import os
from scraper import main

from fastapi import FastAPI
from fastapi.responses import FileResponse
from weasyprint import HTML
import os
from scraper import main

app = FastAPI()

@app.get("/")
def home():
    return {"status": "API funcionando"}

@app.get("/catalog")
def run_catalog():
    try:
        main()

        file_path = "Catalogo_2026.html"

        if not os.path.exists(file_path):
            return {"error": "No se generó el HTML"}

        return FileResponse(file_path, media_type="text/html")

    except Exception as e:
        return {"error": str(e)}

@app.get("/catalog-pdf")
def catalog_pdf():
    try:
        main()

        html_file = "Catalogo_2026.html"
        pdf_file = "Catalogo_2026.pdf"

        if not os.path.exists(html_file):
            return {"error": "No se generó el HTML"}

        HTML(filename=html_file).write_pdf(pdf_file)

        return FileResponse(
            pdf_file,
            media_type="application/pdf",
            filename="Catalogo_2026.pdf"
        )

    except Exception as e:
        return {"error": str(e)}