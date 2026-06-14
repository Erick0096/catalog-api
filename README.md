Paso 1. Preparar FastAPI creando el proyecto
catalog-api/
  │
  ├── app.py
  ├── scraper.py
  ├── requirements.txt
  ├── Productos_urls.txt
  ├── Catalogo_2026.html (Creada por scraper.py)
  ├── Productos.json (Creada por scraper.py)

Paso 2. 
pip install -r requirements.txt
python -m uvicorn app:app --reload

Paso 3.
Cargar HTML desde http://localhost:8000/catalog

Paso 4. Desde la carpeta de origen subir a GitHub
git init
git add .
git commit -m "API scraper"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/catalog-api.git
git push -u origin main


Paso 5. Deploy en Render
Crear cuenta desde https://render.com
Click en New
Selecciona:
Web Service
Conectar el repositorio cargado en GitHub y llenar Basic Settings con:

Name: catalog-api
Region: (cualquiera cercana)
Branch: main

6. Build & Deploy
Build Command:
pip install -r requirements.txt

Start Command:
uvicorn app:app --host 0.0.0.0 --port 10000

Deploy 
Click en Create Web Service
despues de unos minutos Rendr devuelve https://catalog-api.onrender.com

Test  https://catalog-api.onrender.com/catalog
