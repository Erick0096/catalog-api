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
https://github.com/new
Nombre: catalog-api
NO marques “Initialize with README”
Crear repositorio
git init
git add .
git commit -m "API scraper"
git branch -M main
git remote add origin https://github.com/Erick0096/catalog-api.git
git remote -v
Generar un token desde https://github.com/settings/developersettings/personalaccesstokens/tokens
Nombre:API_n8n
Click en "Generate new Tokens (classic)"
Selecciona:repo (Full control of private repositories)
Copia el token : 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

git push -u origin main
Autorize credentials
Erick0096
Contraseña: Token
Para no repetir el Login
git config --global credential.helper store

Paso 5. Deploy en Render
Crear cuenta desde https://render.com
Click en New
Selecciona:
Web Service
Git repository y escoger catalog-api
Conectar el repositorio cargado en GitHub y llenar Basic Settings con:

Name: catalog-api
Region: (cualquiera cercana)
Branch: main
Build Command:pip install -r requirements.txt
Start Command: uvicorn app:app --host 0.0.0.0 --port 10000
Click en Deploy Web Service

6. Despues de unos minutos Render devuelve https://catalog-api-el45.onrender.com

7.Test en https://catalog-api.onrender.com/catalog

8. n8n Conection
Nodo: HTTP Request
Method: GET
URL: https://catalog-api-el45.onrender.com/catalog-pdf
Response Format: File
En Output:Dar Download para corroborar

Nodo: Gmail
HTML: {{$binary.data.toString()}}

Nota: cuando se agrega una libreria nueva a requirement.txt; por ejemplo, la libreria que convierte de html a pdf "weasyprint" se debe ejecutar lo siguiente, esto para que Git pase a Github los commits, y así Render instale la librería durante el deploy. 
git add .
git commit -m "Agregar weasyprint y modificación de app.py"
git push origin main
git status



