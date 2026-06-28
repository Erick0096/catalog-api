# -*- coding: utf-8 -*-
"""
Script profesional para generar un catálogo HTML a partir de productos de StyleKorean.
Incluye scraping, traducción al español, formateo de descripciones y cálculo de precios en CRC.
El HTML resultante está optimizado para conversión a PDF (sin lazy loading, sin botones interactivos).
"""

import urllib.request
import json
import re
import ssl
from html import escape
from datetime import datetime
import time
import hashlib
from difflib import SequenceMatcher
import urllib.parse
from deep_translator import GoogleTranslator

# -----------------------------------------------------------------------------
# CONSTANTES DE CONFIGURACIÓN
# -----------------------------------------------------------------------------

USD_TO_CRC = 465               # Tipo de cambio fijo
TIEMPO_ENTRE_PETICIONES = 0.5  # Segundos entre solicitudes
TAMANO_LOTE = 50               # Cada cuántos productos guardar progreso
MAX_INTENTOS = 3               # Reintentos por fallo de red


def redondear_precio_crc(precio):
    """
    Redondea un precio en CRC hacia arriba al siguiente múltiplo de 100.
    Ejemplos: 9501 -> 9600, 10000 -> 10000.
    """
    if not precio or precio <= 0:
        return precio
    if precio % 100 == 0:
        return precio
    return ((precio // 100) + 1) * 100


# -----------------------------------------------------------------------------
# TRADUCTOR CON CACHÉ
# -----------------------------------------------------------------------------

class TraductorIlimitado:
    """
    Traduce textos del inglés al español usando Google Translator (deep-translator).
    Implementa caché en memoria para evitar traducciones repetidas.
    """

    def __init__(self):
        self.cache = {}                     # Almacén de traducciones
        self.estadisticas = {
            'cache_hits': 0,
            'cache_misses': 0,
            'errores': 0
        }
        self.translator = GoogleTranslator(source='en', target='es')

    def _obtener_clave_cache(self, texto):
        """Genera una clave única para el texto a traducir."""
        return hashlib.md5(texto.encode('utf-8')).hexdigest()

    def traducir(self, texto, max_intentos=3):
        """
        Traduce el texto, usando caché si está disponible.
        Si falla, reintenta hasta max_intentos veces.
        """
        if not texto or len(texto) < 20:
            return texto

        # Limitar longitud para evitar problemas con la API
        if len(texto) > 4900:
            texto_corto = texto[:4900]
            ultimo_punto = texto_corto.rfind('.')
            if ultimo_punto > 500:
                texto = texto[:ultimo_punto + 1] + "..."
            else:
                texto = texto[:4900] + "..."

        clave = self._obtener_clave_cache(texto)

        if clave in self.cache:
            self.estadisticas['cache_hits'] += 1
            return self.cache[clave]

        self.estadisticas['cache_misses'] += 1

        for intento in range(max_intentos):
            try:
                texto_traducido = self.translator.translate(texto)
                self.cache[clave] = texto_traducido
                time.sleep(0.2)  # Pequeña pausa para respetar límites de la API
                return texto_traducido
            except Exception as e:
                print(f"     [ADVERTENCIA] Intento {intento+1} fallo: {str(e)[:50]}")
                time.sleep(2)

        self.estadisticas['errores'] += 1
        return texto

    def mostrar_estadisticas(self):
        """Imprime estadísticas de uso del caché."""
        total = self.estadisticas['cache_hits'] + self.estadisticas['cache_misses']
        if total > 0:
            hit_rate = (self.estadisticas['cache_hits'] / total) * 100
            print(f"   Caché: {self.estadisticas['cache_hits']} aciertos ({hit_rate:.1f}%)")
        print(f"   Errores: {self.estadisticas['errores']}")


# -----------------------------------------------------------------------------
# FUNCIONES DE FORMATEO DE DESCRIPCIÓN
# -----------------------------------------------------------------------------

def formatear_descripcion(texto_descripcion, nombre_producto):
    """
    Convierte una descripción larga en un texto estructurado con secciones y viñetas.
    Elimina redundancias con el nombre del producto.
    """
    if not texto_descripcion or len(texto_descripcion) < 30:
        return texto_descripcion

    nombre_limpio = nombre_producto.split('|')[0].strip()

    # Eliminar el nombre del producto si aparece al inicio
    if texto_descripcion.startswith(nombre_limpio):
        texto_descripcion = texto_descripcion[len(nombre_limpio):].strip()
        texto_descripcion = re.sub(r'^[:;\-\s]+', '', texto_descripcion)

    patron_nombre = re.compile(r'^' + re.escape(nombre_limpio) + r'\s*[:;\-]*\s*', re.IGNORECASE)
    texto_descripcion = patron_nombre.sub('', texto_descripcion)

    # Definir secciones (sin emojis)
    secciones = {
        "DESCRIPCION": [],
        "INGREDIENTES CLAVE": [],
        "PROPIEDADES": [],
        "MODO DE USO": [],
        "CARACTERISTICAS": []
    }

    # Palabras clave para clasificar oraciones
    beneficios_keywords = ['ayuda a', 'reduce', 'mejora', 'previene', 'controla', 'aumenta', 'promueve',
                           'hidrata', 'calma', 'nutre', 'protege', 'suaviza', 'fortalece', 'estimula']
    ingredientes_keywords = ['extracto de', 'aceite de', 'vitamina', 'ácido', 'colágeno', 'retinol',
                             'niacinamida', 'glicerina', 'ceramida', 'centella', 'ácido hialurónico']
    uso_keywords = ['aplicar', 'usar', 'masajear', 'extender', 'enjuagar', 'dejar actuar',
                    'modo de uso', 'cómo usar', 'instrucciones']

    # Dividir en oraciones
    oraciones = re.split(r'[.!?]+', texto_descripcion)
    oraciones = [o.strip() for o in oraciones if len(o.strip()) > 15]

    # Clasificar cada oración
    for oracion in oraciones:
        oracion_lower = oracion.lower()

        # Limpiar cualquier mención del nombre dentro de la oración
        if nombre_limpio.lower() in oracion_lower:
            oracion = re.sub(re.escape(nombre_limpio), '', oracion, flags=re.IGNORECASE)
            oracion = re.sub(r'^[:;\-\s]+', '', oracion).strip()

        if any(keyword in oracion_lower for keyword in beneficios_keywords):
            secciones["DESCRIPCION"].append(oracion)
        elif any(keyword in oracion_lower for keyword in ingredientes_keywords):
            secciones["INGREDIENTES CLAVE"].append(oracion)
        elif any(keyword in oracion_lower for keyword in uso_keywords):
            secciones["MODO DE USO"].append(oracion)
        elif any(word in oracion_lower for word in ['textura', 'absorción', 'sensación', 'fórmula']):
            secciones["PROPIEDADES"].append(oracion)
        else:
            secciones["CARACTERISTICAS"].append(oracion)

    # Construir el texto formateado
    partes_formateadas = []

    for titulo, contenido in secciones.items():
        if contenido:
            partes_formateadas.append(titulo.upper())
            for item in contenido[:5]:  # Máximo 5 items por sección
                if len(item) > 10:
                    item_limpio = item.strip()
                    item_limpio = re.sub(re.escape(nombre_limpio), '', item_limpio, flags=re.IGNORECASE)
                    item_limpio = re.sub(r'^[:;\-\s]+', '', item_limpio)
                    item_limpio = re.sub(r'\s+', ' ', item_limpio)
                    if item_limpio:
                        partes_formateadas.append(f"  - {item_limpio}")

    # Si no se pudo estructurar, usar viñetas simples
    if len(partes_formateadas) <= 1:
        partes_formateadas = []
        puntos_clave = []
        frases = re.findall(r'[A-Za-zÁÉÍÓÚáéíóú][^.!?]*[.!?]', texto_descripcion)
        for frase in frases[:8]:
            if 20 < len(frase) < 150:
                frase_limpia = frase.strip()
                frase_limpia = re.sub(re.escape(nombre_limpio), '', frase_limpia, flags=re.IGNORECASE)
                frase_limpia = re.sub(r'^[:;\-\s]+', '', frase_limpia)
                frase_limpia = re.sub(r'\s+', ' ', frase_limpia).strip()
                if frase_limpia:
                    puntos_clave.append(f"  - {frase_limpia}")

        if puntos_clave:
            partes_formateadas.append("DETALLES DEL PRODUCTO")
            partes_formateadas.extend(puntos_clave)
        else:
            # Último recurso: dividir en párrafos
            parrafos = texto_descripcion.split('\n')
            for parrafo in parrafos[:6]:
                if len(parrafo) > 30:
                    parrafo_limpio = re.sub(re.escape(nombre_limpio), '', parrafo, flags=re.IGNORECASE)
                    parrafo_limpio = re.sub(r'^[:;\-\s]+', '', parrafo_limpio).strip()
                    if parrafo_limpio:
                        partes_formateadas.append(f"  - {parrafo_limpio[:200]}")

    resultado = '\n'.join(partes_formateadas)

    # Limitar longitud total
    if len(resultado) > 1800:
        resultado = resultado[:1800] + "..."

    return resultado


# -----------------------------------------------------------------------------
# FUNCIONES DE BÚSQUEDA EN INTERNET (FUENTES ALTERNATIVAS)
# -----------------------------------------------------------------------------

def buscar_descripcion_en_internet(nombre_producto):
    """
    Busca descripciones del producto usando DuckDuckGo Lite (gratuito, sin API).
    Devuelve el mejor snippet encontrado o None.
    """
    print("     Buscando en internet...", end="")
    try:
        query = nombre_producto.replace("|", "").strip()[:100]
        query_codificada = urllib.parse.quote(query)
        url = f"https://lite.duckduckgo.com/lite/?q={query_codificada}+review+description"

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
            html = response.read().decode('utf-8', errors='ignore')
            snippets = re.findall(r'<td class="result-snippet">(.*?)<tr>', html, re.DOTALL)

            mejores_descripciones = []
            for snippet in snippets:
                snippet = re.sub(r'<[^>]+>', ' ', snippet)
                snippet = re.sub(r'\s+', ' ', snippet).strip()
                if 80 < len(snippet) < 800:
                    if not re.search(r'Sponsored|Ad|Amazon|eBay|Walmart', snippet, re.I):
                        mejores_descripciones.append((len(snippet), snippet))

            if mejores_descripciones:
                mejores_descripciones.sort(reverse=True)
                descripcion = mejores_descripciones[0][1]
                print(f" OK ({len(descripcion)} caracteres)")
                return descripcion

            print(" No encontrada")
            return None

    except Exception as e:
        print(f" Error: {str(e)[:50]}")
        return None


def buscar_descripcion_en_olivia(nombre_producto):
    """
    Busca en Olivia Costa Rica (tienda coreana) como fuente alternativa.
    """
    try:
        query = nombre_producto.lower()
        palabras = query.split()
        query_simple = ' '.join(palabras[:4]) if len(palabras) > 3 else query
        query_codificada = urllib.parse.quote(query_simple)
        url = f"https://oliviacostarica.com/search?q={query_codificada}"

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            html = response.read().decode('utf-8', errors='ignore')
            descripciones = re.findall(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>', html, re.IGNORECASE | re.DOTALL)
            for desc in descripciones:
                desc_limpia = re.sub(r'<[^>]+>', ' ', desc)
                desc_limpia = re.sub(r'\s+', ' ', desc_limpia).strip()
                if 80 < len(desc_limpia) < 800:
                    return desc_limpia
    except:
        pass
    return None


# -----------------------------------------------------------------------------
# FUNCIONES DE LIMPIEZA DE TEXTO
# -----------------------------------------------------------------------------

def limpiar_nombre_producto(nombre):
    """Elimina sufijos y caracteres extraños del nombre del producto."""
    if not nombre:
        return "Producto Song Beauty Shop"
    nombre = re.sub(r'\s*\|.*$', '', nombre)
    nombre = re.sub(r'\s*-\s*StyleKorean.*$', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\[.*?\]', '', nombre)
    nombre = re.sub(r'\(.*?\)', '', nombre)
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    if len(nombre) < 5:
        nombre = "Producto Coreano Premium"
    return nombre


def limpiar_caracteres_especiales(texto):
    """Reemplaza entidades HTML y caracteres problemáticos."""
    if not texto:
        return ""
    entidades = {
        '&gt;': '>', '&lt;': '<', '&amp;': '&', '&quot;': '"',
        '&#39;': "'", '&nbsp;': ' ', '&deg;': '°', '&plusmn;': '±',
        '&times;': '×', '&divide;': '÷', '&frac12;': '½', '&frac14;': '¼',
        '&frac34;': '¾',
    }
    for entidad, caracter in entidades.items():
        texto = texto.replace(entidad, caracter)

    # Eliminar caracteres no imprimibles
    texto = re.sub(r'[^\x20-\x7E\u00A0-\u00FF\u0100-\u017F\u2010-\u2027]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def limpiar_descripcion(texto, nombre_producto=None):
    """
    Elimina etiquetas HTML, enlaces y texto redundante (similar al nombre del producto).
    """
    if not texto:
        return ""
    texto = re.sub(r'<br\s*/?>', '\n', texto)
    texto = re.sub(r'</p>', '\n', texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = limpiar_caracteres_especiales(texto)
    texto = re.sub(r'https?://[^\s]+', '', texto)
    texto = re.sub(r'\*{3,}', '', texto)

    if nombre_producto and len(nombre_producto) > 5:
        palabras_nombre = set(nombre_producto.lower().split())
        lineas = texto.split('\n')
        lineas_limpias = []
        for linea in lineas:
            linea_limpia = linea.strip()
            if not linea_limpia or len(linea_limpia) < 10:
                continue
            palabras_linea = set(linea_limpia.lower().split())
            if palabras_linea and palabras_nombre:
                interseccion = palabras_linea.intersection(palabras_nombre)
                union = palabras_linea.union(palabras_nombre)
                similitud = len(interseccion) / len(union) if union else 0
                if similitud > 0.5:
                    continue
            lineas_limpias.append(linea_limpia)
        texto = '\n'.join(lineas_limpias)

    texto = re.sub(r'\n\s*\n', '\n', texto)
    texto = re.sub(r'[ \t]+', ' ', texto)
    return texto.strip()


# -----------------------------------------------------------------------------
# EXTRACCIÓN DE LA DESCRIPCIÓN DESDE EL HTML
# -----------------------------------------------------------------------------

def extraer_descripcion_desde_tabcontent(html):
    """Extrae descripción del div con id 'main_tabcontent_yk0' (estilo StyleKorean)."""
    patron = r'<div[^>]*id="main_tabcontent_yk0"[^>]*>(.*?)</div>\s*</div>\s*<div[^>]*id="main_tabcontent_yk1"'
    match = re.search(patron, html, re.IGNORECASE | re.DOTALL)
    if not match:
        patron_simple = r'<div[^>]*id="main_tabcontent_yk0"[^>]*>(.*?)</div>\s*</div>'
        match = re.search(patron_simple, html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    return None


def extraer_descripcion_desde_div_general(html):
    """Método alternativo: busca secciones como Description, Ingredients, Suggested Use."""
    secciones = []
    desc_match = re.search(r'<b>Description</b>(.*?)(?=<b>|$)', html, re.IGNORECASE | re.DOTALL)
    if desc_match:
        secciones.append(desc_match.group(1))
    ing_match = re.search(r'<b>Ingredients?</b>(.*?)(?=<b>|$)', html, re.IGNORECASE | re.DOTALL)
    if ing_match:
        secciones.append(f"Ingredients: {ing_match.group(1)}")
    use_match = re.search(r'<b>Suggested Use</b>(.*?)(?=<b>|$)', html, re.IGNORECASE | re.DOTALL)
    if use_match:
        secciones.append(f"How to Use: {use_match.group(1)}")
    if secciones:
        return " | ".join(secciones)
    return None


def extraer_descripcion_real_producto(html, product_name):
    """
    Combina las estrategias anteriores para obtener la descripción más completa.
    """
    print("     Buscando descripcion...", end="")
    contenido_raw = extraer_descripcion_desde_tabcontent(html)
    if contenido_raw:
        print(" OK (StyleKorean)")
        return limpiar_descripcion(contenido_raw, product_name)

    secciones_raw = extraer_descripcion_desde_div_general(html)
    if secciones_raw:
        print(" OK (secciones)")
        return limpiar_descripcion(secciones_raw, product_name)

    print(" No encontrada")
    return None


# -----------------------------------------------------------------------------
# GENERACIÓN DE DESCRIPCIÓN GENÉRICA (CUANDO NO HAY DATOS)
# -----------------------------------------------------------------------------

def generar_descripcion_generica(nombre):
    """
    Crea una descripción por defecto según el tipo de producto (mask, cleansing, etc.)
    """
    nombre_lower = nombre.lower()

    descripciones = {
        'mask': """DESCRIPCION
  - Hidrata intensamente la piel
  - Calma irritaciones y enrojecimiento
  - Mejora la textura y luminosidad

INGREDIENTES CLAVE
  - Extractos naturales coreanos
  - Formula con ingredientes hidratantes

MODO DE USO
  - Aplicar sobre el rostro limpio
  - Dejar actuar 15-20 minutos
  - Retirar con agua tibia""",

        'cleansing': """DESCRIPCION
  - Elimina suavemente impurezas y maquillaje
  - Respeta la barrera natural de la piel
  - Deja la piel fresca sin tirantez

INGREDIENTES CLAVE
  - Formula suave sin irritantes
  - Extractos naturales purificantes

MODO DE USO
  - Aplicar sobre el rostro humedo
  - Masajear suavemente
  - Enjuagar con agua tibia""",

        'sunscreen': """DESCRIPCION
  - Proteccion SPF50+ PA++++
  - Bloquea rayos UVA y UVB
  - Previene el fotoenvejecimiento

PROPIEDADES
  - Textura ligera sin residuos blancos
  - Absorcion rapida y no grasa

MODO DE USO
  - Aplicar como ultimo paso del skincare
  - Usar diariamente incluso en dias nublados""",

        'serum': """DESCRIPCION
  - Trata preocupaciones especificas
  - Alta concentracion de activos
  - Resultados visibles en pocas semanas

INGREDIENTES CLAVE
  - Formula con ingredientes activos coreanos

MODO DE USO
  - Aplicar despues del tonico
  - Usar antes de la crema hidratante""",

        'cream': """DESCRIPCION
  - Hidratacion profunda y duradera
  - Sella la humedad en la piel
  - Nutre y protege la barrera cutanea

PROPIEDADES
  - Textura suave y cremosa
  - Rapida absorcion sin sensacion grasa

MODO DE USO
  - Aplicar como ultimo paso del skincare
  - Usar manana y noche para mejores resultados""",

        'jelly': """DESCRIPCION
  - Ayuda a controlar el peso corporal
  - Reduce la sensacion de hambre
  - Promueve la digestion saludable

INGREDIENTES CLAVE
  - Extracto de Garcinia Cambogia
  - Fibra de granada y chia
  - Maltodextrina resistente

MODO DE USO
  - Consumir antes de las comidas principales
  - Acompanar con suficiente agua"""
    }

    for key, desc in descripciones.items():
        if key in nombre_lower:
            return desc

    # Descripción genérica por defecto
    return f"""DESCRIPCION
  - Producto original de Corea del Sur
  - Formulado con ingredientes de alta calidad
  - Tecnologia avanzada de belleza coreana

MODO DE USO
  - Sigue las instrucciones del empaque
  - Para mejores resultados, usa consistentemente"""


# -----------------------------------------------------------------------------
# CÁLCULO DE PRECIOS
# -----------------------------------------------------------------------------

def calcular_precio_crc(precio_usd):
    """
    Convierte precio en USD a CRC aplicando markup según rangos.
    Luego redondea al múltiplo de 100 superior.
    """
    if not precio_usd:
        return None
    match = re.search(r'(\d+(?:\.\d{2})?)', str(precio_usd))
    if not match:
        return None

    valor_usd = float(match.group(1))

    if 10 <= valor_usd <= 27:
        markup = 1.35
    elif 27 < valor_usd <= 38:
        markup = 1.25
    elif valor_usd > 38:
        markup = 1.15
    else:
        markup = 1.35

    precio_final_usd = valor_usd * markup
    precio_final_crc = round(precio_final_usd * USD_TO_CRC)
    precio_final_crc = redondear_precio_crc(precio_final_crc)
    return precio_final_crc


def format_price_crc(price):
    """Formatea el precio en CRC con el símbolo de colón y separadores de miles."""
    if price and price > 0:
        return f"₡{price:,}"
    return "Consultar precio"


# -----------------------------------------------------------------------------
# EXTRACCIÓN DE DATOS DEL PRODUCTO (NOMBRE, PRECIO, IMAGEN, DESCRIPCIÓN)
# -----------------------------------------------------------------------------

def extract_product_info(html, url, traductor):
    """
    Procesa el HTML de una página de producto y devuelve un diccionario con
    nombre, precios, descripción formateada y URL de la imagen.
    """
    product = {
        "name": "Nombre no encontrado",
        "price_usd": None,
        "price_crc": None,
        "description": "",
        "imageUrl": None,
    }

    # --- Nombre ---
    title_patterns = [
        r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"',
        r'<h1[^>]*itemprop="name"[^>]*>([^<]+)</h1>',
        r'<h1[^>]*class="[^"]*product[^"]*title[^"]*"[^>]*>([^<]+)</h1>',
        r'<h1[^>]*>([^<]+)</h1>',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            product["name"] = limpiar_nombre_producto(match.group(1))
            break

    # --- Precio ---
    price_patterns = [
        r'<meta[^>]*property="product:price:amount"[^>]*content="([^"]+)"',
        r'<span[^>]*class="[^"]*price[^"]*"[^>]*>\$?\s*(\d+(?:,\d+)?(?:\.\d{2})?)',
        r'<span[^>]*class="[^"]*sale-price[^"]*"[^>]*>\$?\s*(\d+(?:,\d+)?(?:\.\d{2})?)',
        r'<div[^>]*class="[^"]*price[^"]*"[^>]*>\$?\s*(\d+(?:,\d+)?(?:\.\d{2})?)',
        r'\$\s*(\d+(?:,\d+)?(?:\.\d{2})?)\s*(?:USD)?',
    ]
    precios_encontrados = []
    for pattern in price_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if match and match.strip():
                precio_str = match.replace(',', '').strip()
                try:
                    precio_num = float(precio_str)
                    if 1 < precio_num < 1000:
                        precios_encontrados.append(precio_num)
                except:
                    pass

    if precios_encontrados:
        precios_encontrados.sort()
        product["price_usd"] = f"${precios_encontrados[0]:.2f}"
        product["price_crc"] = calcular_precio_crc(product["price_usd"])
        print(f"     Precio: {product['price_usd']} -> ₡{product['price_crc']:,}")

    # --- Descripción ---
    descripcion_limpia = extraer_descripcion_real_producto(html, product["name"])

    if descripcion_limpia and len(descripcion_limpia) > 50:
        print(f"     Descripcion encontrada en StyleKorean ({len(descripcion_limpia)} caracteres)")
        print("     Traduciendo al espanol...", end="")
        texto_traducido = traductor.traducir(descripcion_limpia)
        print(" OK")

        print("     Formateando descripcion...", end="")
        product["description"] = formatear_descripcion(texto_traducido, product["name"])
        print(" OK")
    else:
        print("     No se encontro descripcion en StyleKorean")
        print("     Buscando en internet...")
        descripcion_internet = buscar_descripcion_en_internet(product["name"])

        if descripcion_internet and len(descripcion_internet) > 50:
            print(f"     Descripcion encontrada en internet ({len(descripcion_internet)} caracteres)")
            print("     Traduciendo...", end="")
            texto_traducido = traductor.traducir(descripcion_internet)
            print(" OK")

            print("     Formateando...", end="")
            product["description"] = formatear_descripcion(texto_traducido, product["name"])
            print(" OK")
        else:
            print("     Buscando en Olivia Costa Rica...")
            descripcion_olivia = buscar_descripcion_en_olivia(product["name"])

            if descripcion_olivia and len(descripcion_olivia) > 50:
                print("     Descripcion encontrada en Olivia")
                product["description"] = formatear_descripcion(descripcion_olivia, product["name"])
            else:
                print("     Usando descripcion generica")
                product["description"] = generar_descripcion_generica(product["name"])

    # --- Imagen ---
    image_patterns = [
        r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"',
        r'<img[^>]*class="[^"]*product-image[^"]*"[^>]*src="([^"]+)"',
        r'<img[^>]*id="[^"]*main-image[^"]*"[^>]*src="([^"]+)"',
        r'<img[^>]*data-src="([^"]+\.(?:jpg|jpeg|png|webp))"',
    ]
    for pattern in image_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            img_url = match.group(1)
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                img_url = 'https://www.stylekorean.com' + img_url
            product["imageUrl"] = img_url
            break

    return product


# -----------------------------------------------------------------------------
# SCRAPING DE UN PRODUCTO (CON REINTENTOS)
# -----------------------------------------------------------------------------

def scrape_product(url, traductor, intento=1):
    """
    Realiza la petición HTTP a la URL, extrae la información y devuelve el producto.
    Reintenta hasta MAX_INTENTOS en caso de error.
    """
    print("  Procesando...", end="")
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.8,en;q=0.5',
        }
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            content = response.read()
            # Intentar decodificar con diferentes codificaciones
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    html = content.decode(encoding)
                    break
                except:
                    continue

            product = extract_product_info(html, url, traductor)
            print(f" OK {product['name'][:40]}...")
            return product

    except Exception as e:
        print(f" Error: {str(e)[:50]}")
        if intento < MAX_INTENTOS:
            print(f"     Reintentando ({intento+1}/{MAX_INTENTOS})...")
            time.sleep(2)
            return scrape_product(url, traductor, intento+1)

        return {
            "name": "Error al cargar producto",
            "price_usd": None,
            "price_crc": None,
            "description": "Producto temporalmente no disponible. Consulte disponibilidad.",
            "imageUrl": None,
        }


# -----------------------------------------------------------------------------
# CARGA DE URLs DESDE ARCHIVO
# -----------------------------------------------------------------------------

def cargar_urls():
    """Lee el archivo Productos_urls.txt y devuelve una lista de URLs."""
    try:
        with open('Productos_urls.txt', 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and line.startswith('http')]
        print(f"OK Cargadas {len(urls)} URLs desde Productos_urls.txt")
        return urls
    except FileNotFoundError:
        print("ADVERTENCIA: No se encontro Productos_urls.txt, usando URLs de ejemplo")
        return [
            "https://www.stylekorean.com/shop/foodology-renewal-coleology-cutting-jelly-10-pouch/1768386373/",
        ]


# -----------------------------------------------------------------------------
# GENERACIÓN DEL CATÁLOGO HTML
# -----------------------------------------------------------------------------

def generar_html_catalogo(products):
    """
    Construye el HTML final del catálogo con todas las tarjetas de producto.
    Las imágenes no tienen loading="lazy" para que se carguen al instante.
    No incluye botones interactivos (WhatsApp, carrito).
    """
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")

    html_template = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Song Beauty Shop - Catalogo de Productos</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }

        .header h1 { font-size: 42px; margin-bottom: 10px; }

        .stats-badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 20px;
            border-radius: 50px;
            margin-top: 15px;
        }

        .catalog {
            display: flex;
            flex-direction: column;
            gap: 30px;
            padding: 40px;
            max-width: 1200px;
            margin: 0 auto;
        }

        .product-card {
            background: white;
            border-radius: 20px;
            overflow: hidden;
            display: flex;
            flex-direction: row;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s;
            animation: fadeIn 0.6s ease-out;
        }

        .product-card:hover { transform: translateY(-5px); }

        .product-image-container {
            flex: 0 0 300px;
            background: #f8f9fa;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .product-image {
            width: 100%;
            height: auto;
            max-height: 300px;
            object-fit: contain;
            transition: transform 0.5s;
        }

        .product-card:hover .product-image { transform: scale(1.05); }

        .product-info {
            flex: 1;
            padding: 25px;
            display: flex;
            flex-direction: column;
        }

        .product-name {
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 15px;
            color: #2c3e50;
            line-height: 1.3;
        }

        .price-container { margin: 15px 0 20px 0; }

        .product-price {
            color: #e74c3c;
            font-size: 32px;
            font-weight: 800;
            display: inline-block;
            background: #ffeaa7;
            padding: 8px 20px;
            border-radius: 50px;
        }

        .product-description {
            color: #555;
            font-size: 14px;
            line-height: 1.6;
            margin: 15px 0;
            white-space: pre-wrap;
            background: #f9f9f9;
            padding: 15px;
            border-radius: 12px;
        }

        .product-description strong { color: #2c3e50; }

        .stats {
            text-align: center;
            color: white;
            margin: 30px auto;
            padding: 30px;
            background: rgba(0,0,0,0.1);
            border-radius: 15px;
            max-width: 800px;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 768px) {
            .product-card { flex-direction: column; }
            .product-image-container {
                flex: 0 0 auto;
                height: 250px;
            }
            .product-image {
                width: auto;
                height: 100%;
                max-width: 100%;
            }
            .catalog { padding: 20px; }
            .product-price { font-size: 28px; }
            .header h1 { font-size: 32px; }
            .product-description { font-size: 13px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Song Beauty Shop</h1>
        <p>La belleza que se escucha</p>
        <div class="stats-badge">Productos disponibles: {product_count}</div>
        <p style="font-size: 12px; margin-top: 10px;">Actualizado: {fecha}</p>
    </div>

    <div class="catalog">{product_cards}</div>

    <div class="stats">
        <p>Productos 100% originales de Corea del Sur</p>
        <p>Envios a todo Costa Rica (3-5 dias habiles)</p>
        <p>Aceptamos transferencia, SINPE y efectivo contra entrega</p>
    </div>
</body>
</html>'''

    product_cards = []
    for product in products:
        image_url = product.get('imageUrl', 'https://via.placeholder.com/300x300?text=SongBeauty')
        precio_formateado = format_price_crc(product.get('price_crc'))
        nombre_limpio = product['name'].replace("'", "\\'").replace('"', '&quot;')

        # Convertir saltos de línea a <br> para HTML
        descripcion_html = product.get('description', '')
        descripcion_html = descripcion_html.replace('\n', '<br>')

        card = f'''
        <div class="product-card">
            <div class="product-image-container">
                <img class="product-image" src="{image_url}" alt="{escape(product['name'])}" onerror="this.src='https://via.placeholder.com/300x300?text=SongBeauty'">
            </div>
            <div class="product-info">
                <div class="product-name">{escape(product['name'])}</div>
                <div class="price-container">
                    <span class="product-price">{precio_formateado}</span>
                </div>
                <div class="product-description">{descripcion_html}</div>
            </div>
        </div>'''
        product_cards.append(card)

    final_html = html_template.replace('{product_cards}', '\n'.join(product_cards))
    final_html = final_html.replace('{product_count}', str(len(products)))
    final_html = final_html.replace('{fecha}', fecha_actual)

    return final_html


# -----------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# -----------------------------------------------------------------------------

def main():
    print("\n" + "="*50)
    print("INICIANDO GENERACION DE CATALOGO")
    print("="*50)
    print(f"Tasa de cambio: 1 USD = {USD_TO_CRC} CRC")
    print("Marcups: $10-27 -> 45% | $27-38 -> 30% | >$38 -> 20%")
    print("Busqueda en internet: Activada (DuckDuckGo + Olivia)")
    print("Redondeo de precios: Activado (siempre hacia arriba al siguiente multiplo de 100)")
    print("="*50)

    urls = cargar_urls()
    total_productos = len(urls)
    print(f"\nTotal productos a procesar: {total_productos}")

    if total_productos == 0:
        print("No hay URLs para procesar")
        return

    print("\nInicializando traductor...")
    traductor = TraductorIlimitado()

    productos_procesados = []
    tiempo_inicio = time.time()

    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{total_productos}]")
        producto = scrape_product(url, traductor)
        productos_procesados.append(producto)

        if idx % TAMANO_LOTE == 0:
            with open(f"progreso_{idx}.json", "w", encoding="utf-8") as f:
                json.dump(productos_procesados, f, indent=2, ensure_ascii=False)
            print(f"  Progreso guardado")

        time.sleep(TIEMPO_ENTRE_PETICIONES)

    tiempo_total = time.time() - tiempo_inicio

    print("\n" + "="*50)
    print("ESTADISTICAS DEL PROCESO")
    print("="*50)
    print(f"Tiempo total: {tiempo_total:.1f} segundos")
    print(f"Productos: {len(productos_procesados)}")
    print(f"Promedio: {tiempo_total/len(productos_procesados):.1f} seg/producto")

    traductor.mostrar_estadisticas()

    print("\nGenerando catalogo HTML...")
    html_content = generar_html_catalogo(productos_procesados)

    output_file = "Catalogo_2026.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open("Productos.json", "w", encoding="utf-8") as f:
        json.dump(productos_procesados, f, indent=2, ensure_ascii=False)

    print(f"\nProceso completado exitosamente.")
    print(f"Archivo HTML: {output_file}")
    print("El catalogo esta listo para ser convertido a PDF.")


if __name__ == "__main__":
    main()
    input("\nPresiona Enter para salir...")