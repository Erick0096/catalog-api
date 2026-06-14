
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

print("Scraping script")

# Setting
USD_TO_CRC = 465
TIEMPO_ENTRE_PETICIONES = 0.5
TAMANO_LOTE = 50
MAX_INTENTOS = 3

# Clase para traducir usando libreria deep-translator compatible con Python 3.13
class TraductorIlimitado:
    
    def __init__(self):
        self.cache = {}
        self.estadisticas = {'cache_hits': 0, 'cache_misses': 0, 'errores': 0}
        self.translator = GoogleTranslator(source='en', target='es')
    
    def obtener_clave_cache(self, texto):
        return hashlib.md5(texto.encode('utf-8')).hexdigest()
    
    def traducir(self, texto, max_intentos=3):
        """Traducir texto de inglés a español"""
        if not texto or len(texto) < 20:
            return texto
        
        # Limitar la descripción a 4900 caracteres por seguridad
        if len(texto) > 4900:
            texto_corto = texto[:4900]
            ultimo_punto = texto_corto.rfind('.')
            if ultimo_punto > 500:
                texto = texto[:ultimo_punto + 1] + "..."
            else:
                texto = texto[:4900] + "..."
        
        clave = self.obtener_clave_cache(texto)
        
        if clave in self.cache:
            self.estadisticas['cache_hits'] += 1
            return self.cache[clave]
        
        self.estadisticas['cache_misses'] += 1
        
        for intento in range(max_intentos):
            try:
                # Usando deep-translator
                texto_traducido = self.translator.translate(texto)
                self.cache[clave] = texto_traducido
                time.sleep(0.2)  # Pausa para no saturar
                return texto_traducido
                
            except Exception as e:
                print(f"     ⚠️ Intento {intento+1} falló: {str(e)[:50]}")
                time.sleep(2)
        
        self.estadisticas['errores'] += 1
        return texto
    
    def mostrar_estadisticas(self):
        total = self.estadisticas['cache_hits'] + self.estadisticas['cache_misses']
        if total > 0:
            hit_rate = (self.estadisticas['cache_hits'] / total) * 100
            print(f"   📊 Caché: {self.estadisticas['cache_hits']} aciertos ({hit_rate:.1f}%)")
        print(f"   ❌ Errores: {self.estadisticas['errores']}")

# Funciones de formato de descripción (Convierte una descripción en prosa a un formato estructurado con secciones y viñetas)
def formatear_descripcion(texto_descripcion, nombre_producto):
    
    if not texto_descripcion or len(texto_descripcion) < 30:
        return texto_descripcion
    
    # Eliminar redundancia con el nombre del producto al inicio de la descripción
    nombre_limpio = nombre_producto.split('|')[0].strip()
    
    # Eliminar el nombre del producto si aparece al inicio de la descripción
    if texto_descripcion.startswith(nombre_limpio):
        texto_descripcion = texto_descripcion[len(nombre_limpio):].strip()
        texto_descripcion = re.sub(r'^[:;\-\s✨]+', '', texto_descripcion)
    
    # También eliminar variaciones con ✨
    patron_nombre = re.compile(r'^✨?\s*' + re.escape(nombre_limpio) + r'\s*✨?\s*[:;\-]*\s*', re.IGNORECASE)
    texto_descripcion = patron_nombre.sub('', texto_descripcion)
    
    # Detectar y extraer diferentes secciones comunes
    secciones = {
        "✨ DESCRIPCIÓN": [],
        "🌿 INGREDIENTES CLAVE": [],
        "💪 PROPIEDADES": [],
        "📋 MODO DE USO": [],
        "🌟 CARACTERÍSTICAS": []
    }
    
    # Patrones para detectar beneficios
    beneficios_keywords = ['ayuda a', 'reduce', 'mejora', 'previene', 'controla', 'aumenta', 'promueve', 
                          'hidrata', 'calma', 'nutre', 'protege', 'suaviza', 'fortalece', 'estimula']
    
    # Patrones para ingredientes clave
    ingredientes_keywords = ['extracto de', 'aceite de', 'vitamina', 'ácido', 'colágeno', 'retinol', 
                            'niacinamida', 'glicerina', 'ceramida', 'centella', 'ácido hialurónico']
    
    # Patrones para modo de uso
    uso_keywords = ['aplicar', 'usar', 'masajear', 'extender', 'enjuagar', 'dejar actuar', 
                   'modo de uso', 'cómo usar', 'instrucciones']
    
    # Dividir el texto en oraciones
    oraciones = re.split(r'[.!?]+', texto_descripcion)
    oraciones = [o.strip() for o in oraciones if len(o.strip()) > 15]
    
    # Clasificar cada oración
    for oracion in oraciones:
        oracion_lower = oracion.lower()
        
        # Limpiar cualquier mención del nombre del producto dentro de la oración
        if nombre_limpio.lower() in oracion_lower:
            oracion = re.sub(re.escape(nombre_limpio), '', oracion, flags=re.IGNORECASE)
            oracion = re.sub(r'^[:;\-\s✨]+', '', oracion).strip()
        
        # Clasificar como descripción/beneficio
        if any(keyword in oracion_lower for keyword in beneficios_keywords):
            secciones["✨ DESCRIPCIÓN"].append(oracion)
        # Clasificar como ingrediente
        elif any(keyword in oracion_lower for keyword in ingredientes_keywords):
            secciones["🌿 INGREDIENTES CLAVE"].append(oracion)
        # Clasificar como modo de uso
        elif any(keyword in oracion_lower for keyword in uso_keywords):
            secciones["📋 MODO DE USO"].append(oracion)
        # Propiedades generales
        elif any(word in oracion_lower for word in ['textura', 'absorción', 'sensación', 'fórmula']):
            secciones["💪 PROPIEDADES"].append(oracion)
        else:
            secciones["🌟 CARACTERÍSTICAS"].append(oracion)
    
    # ========== CORRECCIÓN: NO incluir el título del producto ==========
    partes_formateadas = []
    
    # 🔥 ELIMINADO: Ya no se agrega la línea con el nombre del producto
    # partes_formateadas.append(f"✨ {nombre_corto}\n")
    
    # Añadir cada sección que tenga contenido
    for titulo, contenido in secciones.items():
        if contenido:
            partes_formateadas.append(f"{titulo}")
            for item in contenido[:5]:  # Limitar a 5 items por sección
                if len(item) > 10:
                    # Limpieza final del ítem
                    item_limpio = item.strip()
                    # Eliminar cualquier residuo con el nombre del producto
                    item_limpio = re.sub(re.escape(nombre_limpio), '', item_limpio, flags=re.IGNORECASE)
                    item_limpio = re.sub(r'^[:;\-\s✨]+', '', item_limpio)
                    item_limpio = re.sub(r'\s+', ' ', item_limpio)
                    if item_limpio:  # Solo agregar si no quedó vacío
                        partes_formateadas.append(f"  • {item_limpio}")
    
    # Si no se pudo estructurar bien, usar formato de viñetas simples
    if len(partes_formateadas) <= 1:  # Cambiado de 2 a 1 porque ya no hay título
        partes_formateadas = []  # Reiniciar sin el título
        puntos_clave = []
        
        # Extraer puntos clave (frases cortas y significativas)
        frases = re.findall(r'[A-Za-zÁÉÍÓÚáéíóú][^.!?]*[.!?]', texto_descripcion)
        for frase in frases[:8]:
            if len(frase) > 20 and len(frase) < 150:
                frase_limpia = frase.strip()
                # Limpiar nombre del producto
                frase_limpia = re.sub(re.escape(nombre_limpio), '', frase_limpia, flags=re.IGNORECASE)
                frase_limpia = re.sub(r'^[:;\-\s✨]+', '', frase_limpia)
                frase_limpia = re.sub(r'\s+', ' ', frase_limpia).strip()
                if frase_limpia:
                    puntos_clave.append(f"  • {frase_limpia}")
        
        if puntos_clave:
            partes_formateadas.append("📋 DETALLES DEL PRODUCTO")
            partes_formateadas.extend(puntos_clave)
        else:
            # Último recurso: dividir en párrafos con viñetas
            parrafos = texto_descripcion.split('\n')
            for i, parrafo in enumerate(parrafos[:6]):
                if len(parrafo) > 30:
                    parrafo_limpio = re.sub(re.escape(nombre_limpio), '', parrafo, flags=re.IGNORECASE)
                    parrafo_limpio = re.sub(r'^[:;\-\s✨]+', '', parrafo_limpio).strip()
                    if parrafo_limpio:
                        partes_formateadas.append(f"  • {parrafo_limpio[:200]}")
    
    resultado = '\n'.join(partes_formateadas)
    
    # Limitar longitud total
    if len(resultado) > 1800:
        resultado = resultado[:1800] + "..."
    
    return resultado

def extraer_y_formatear_descripcion(html, nombre_producto, traductor):
    """Extrae, traduce y formatea la descripción del producto"""
    
    # Extraer descripción original
    descripcion_raw = extraer_descripcion_real_producto(html, nombre_producto)
    
    if descripcion_raw and len(descripcion_raw) > 50:
        print(f"     📝 Descripción encontrada ({len(descripcion_raw)} caracteres)")
        print(f"     🌎 Traduciendo al español...", end="")
        texto_traducido = traductor.traducir(descripcion_raw)
        print(f" ✅")
        
        # Formatear la descripción traducida
        print(f"     📋 Formateando descripción...", end="")
        texto_formateado = formatear_descripcion(texto_traducido, nombre_producto)
        print(f" ✅")
        return texto_formateado
    
    return generar_descripcion_generica(nombre_producto)

# ==================== FUNCIONES DE BÚSQUEDA EN INTERNET ====================
def buscar_descripcion_en_internet(nombre_producto):
    """Busca descripción del producto en internet usando DuckDuckGo (gratuito)"""
    
    print(f"     🌐 Buscando en internet...", end="")
    
    try:
        # Limpiar el nombre para la búsqueda
        query = nombre_producto.replace("|", "").strip()
        query = query[:100]  # Limitar longitud
        
        # Codificar la consulta
        query_codificada = urllib.parse.quote(query)
        
        # Usar DuckDuckGo Lite (versión ligera, sin JavaScript)
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
            
            # Extraer snippets de resultados
            snippets = re.findall(r'<td class="result-snippet">(.*?)</td>', html, re.DOTALL)
            
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
                print(f" ✅ encontrada ({len(descripcion)} caracteres)")
                return descripcion
            
            print(f" ❌ no encontrada")
            return None
            
    except Exception as e:
        print(f" ⚠️ error: {str(e)[:50]}")
        return None

def buscar_descripcion_en_olivia(nombre_producto):
    """Busca descripción en Olivia (tienda coreana) como fuente alternativa"""
    
    try:
        query = nombre_producto.lower()
        palabras = query.split()
        if len(palabras) > 3:
            query_simple = ' '.join(palabras[:4])
        else:
            query_simple = query
        
        query_codificada = urllib.parse.quote(query_simple)
        url = f"https://oliviacostarica.com/search?q={query_codificada}"
        
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
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

# ==================== FUNCIONES DE LIMPIEZA ====================
def limpiar_nombre_producto(nombre):
    if not nombre:
        return "Producto My Beauty Store"
    
    nombre = re.sub(r'\s*\|.*$', '', nombre)
    nombre = re.sub(r'\s*-\s*StyleKorean.*$', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\[.*?\]', '', nombre)
    nombre = re.sub(r'\(.*?\)', '', nombre)
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    
    if len(nombre) < 5:
        nombre = "Producto Coreano Premium"
    
    return nombre

def limpiar_caracteres_especiales(texto):
    """Limpia caracteres especiales y entidades HTML"""
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
    
    texto = re.sub(r'[^\x20-\x7E\u00A0-\u00FF\u0100-\u017F\u2010-\u2027\u2600-\u27BF]', ' ', texto)
    texto = re.sub(r'â[\x80-\xFF]{1,2}', ' ', texto)
    texto = re.sub(r'[â¢]', ' ', texto)
    
    texto = texto.replace('â€“', '-')
    texto = texto.replace('â€™', "'")
    texto = texto.replace('â€œ', '"')
    texto = texto.replace('â€', '"')
    texto = texto.replace('Â°', '°')
    texto = texto.replace('ÂºC', '°C')
    texto = texto.replace('â„¢', '™')
    
    texto = re.sub(r'\s+', ' ', texto)
    
    return texto.strip()

def limpiar_descripcion(texto, nombre_producto=None):
    """Limpia la descripción de etiquetas HTML, caracteres especiales y texto redundante"""
    if not texto:
        return ""
    
    texto = re.sub(r'<br\s*/?>', '\n', texto)
    texto = re.sub(r'</p>', '\n', texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = limpiar_caracteres_especiales(texto)
    texto = re.sub(r'https?://[^\s]+', '', texto)
    texto = re.sub(r'\*{3,}', '', texto)
    texto = re.sub(r'(?i)^\s*(?:Q&A|Q & A|Questions|Answers)\s*$', '', texto, flags=re.MULTILINE)
    
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
    texto = texto.strip()
    
    return texto

# ==================== FUNCIONES DE PRECIO ====================
def calcular_precio_crc(precio_usd):
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
    
    return precio_final_crc

def format_price_crc(price):
    if price and price > 0:
        return f"₡{price:,}"
    return "Consultar precio"

# ==================== EXTRACCIÓN DE LA DESCRIPCIÓN ====================
def extraer_descripcion_desde_tabcontent(html):
    """Extrae la descripción del div id='main_tabcontent_yk0'"""
    
    patron_tabcontent = r'<div[^>]*id="main_tabcontent_yk0"[^>]*>(.*?)</div>\s*</div>\s*<div[^>]*id="main_tabcontent_yk1"'
    match = re.search(patron_tabcontent, html, re.IGNORECASE | re.DOTALL)
    
    if not match:
        patron_simple = r'<div[^>]*id="main_tabcontent_yk0"[^>]*>(.*?)</div>\s*</div>'
        match = re.search(patron_simple, html, re.IGNORECASE | re.DOTALL)
    
    if match:
        contenido_tab = match.group(1)
        return contenido_tab
    
    return None

def extraer_descripcion_desde_div_general(html):
    """Método alternativo: buscar cualquier div con texto de descripción"""
    
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
    """Estrategia combinada para extraer la descripción real"""
    
    print(f"     🔍 Buscando descripción...", end="")
    
    contenido_raw = extraer_descripcion_desde_tabcontent(html)
    if contenido_raw:
        print(f" ✅ (StyleKorean)")
        return limpiar_descripcion(contenido_raw, product_name)
    
    secciones_raw = extraer_descripcion_desde_div_general(html)
    if secciones_raw:
        print(f" ✅ (secciones)")
        return limpiar_descripcion(secciones_raw, product_name)
    
    print(f" ❌")
    return None

# ==================== EXTRACCIÓN DE PRODUCTOS ====================
def extract_product_info(html, url, traductor):
    product = {
        "name": "Nombre no encontrado",
        "price_usd": None,
        "price_crc": None,
        "description": "",
        "imageUrl": None,
    }
    
    # ========== NOMBRE ==========
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
    
    # ========== PRECIO ==========
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
        print(f"     Precio: {product['price_usd']} → ₡{product['price_crc']:,}")
    
    # ========== DESCRIPCIÓN MEJORADA Y FORMATEADA ==========
    descripcion_limpia = extraer_descripcion_real_producto(html, product["name"])
    
    if descripcion_limpia and len(descripcion_limpia) > 50:
        print(f"     📝 Descripción encontrada en StyleKorean ({len(descripcion_limpia)} caracteres)")
        print(f"     🌎 Traduciendo al español...", end="")
        texto_traducido = traductor.traducir(descripcion_limpia)
        print(f" ✅")
        
        print(f"     📋 Formateando descripción con secciones...", end="")
        product["description"] = formatear_descripcion(texto_traducido, product["name"])
        print(f" ✅")
    else:
        print(f"     ⚠️ No se encontró descripción en StyleKorean")
        
        print(f"     🔍 Buscando descripción en internet...")
        descripcion_internet = buscar_descripcion_en_internet(product["name"])
        
        if descripcion_internet and len(descripcion_internet) > 50:
            print(f"     📝 Descripción encontrada en internet ({len(descripcion_internet)} caracteres)")
            print(f"     🌎 Traduciendo al español...", end="")
            texto_traducido = traductor.traducir(descripcion_internet)
            print(f" ✅")
            
            print(f"     📋 Formateando descripción...", end="")
            product["description"] = formatear_descripcion(texto_traducido, product["name"])
            print(f" ✅")
        else:
            print(f"     🔍 Buscando en Olivia Costa Rica...")
            descripcion_olivia = buscar_descripcion_en_olivia(product["name"])
            
            if descripcion_olivia and len(descripcion_olivia) > 50:
                print(f"     📝 Descripción encontrada en Olivia")
                product["description"] = formatear_descripcion(descripcion_olivia, product["name"])
            else:
                print(f"     ⚠️ Usando descripción genérica")
                product["description"] = generar_descripcion_generica(product["name"])
    
    # ========== IMAGEN ==========
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

def generar_descripcion_generica(nombre):
    """Genera una descripción genérica formateada en español si no se encuentra la real"""
    nombre_lower = nombre.lower()
    
    descripciones_genericas = {
        'mask': """✨ DESCRIPCIÓN
  • Hidrata intensamente la piel
  • Calma irritaciones y enrojecimiento
  • Mejora la textura y luminosidad

🌿 INGREDIENTES CLAVE
  • Extractos naturales coreanos
  • Fórmula con ingredientes hidratantes

📋 MODO DE USO
  • Aplicar sobre el rostro limpio
  • Dejar actuar 15-20 minutos
  • Retirar con agua tibia""",

        'cleansing': """✨ DESCRIPCIÓN
  • Elimina suavemente impurezas y maquillaje
  • Respeta la barrera natural de la piel
  • Deja la piel fresca sin tirantez

🌿 INGREDIENTES CLAVE
  • Fórmula suave sin irritantes
  • Extractos naturales purificantes

📋 MODO DE USO
  • Aplicar sobre el rostro húmedo
  • Masajear suavemente
  • Enjuagar con agua tibia""",

        'sunscreen': """✨ DESCRIPCIÓN
  • Protección SPF50+ PA++++
  • Bloquea rayos UVA y UVB
  • Previene el fotoenvejecimiento

💪 PROPIEDADES
  • Textura ligera sin residuos blancos
  • Absorción rápida y no grasa

📋 MODO DE USO
  • Aplicar como último paso del skincare
  • Usar diariamente incluso en días nublados""",

        'serum': """✨ DESCRIPCIÓN
  • Trata preocupaciones específicas
  • Alta concentración de activos
  • Resultados visibles en pocas semanas

🌿 INGREDIENTES CLAVE
  • Fórmula con ingredientes activos coreanos

📋 MODO DE USO
  • Aplicar después del tónico
  • Usar antes de la crema hidratante""",

        'cream': """✨ DESCRIPCIÓN
  • Hidratación profunda y duradera
  • Sella la humedad en la piel
  • Nutre y protege la barrera cutánea

💪 PROPIEDADES
  • Textura suave y cremosa
  • Rápida absorción sin sensación grasa

📋 MODO DE USO
  • Aplicar como último paso del skincare
  • Usar mañana y noche para mejores resultados""",

        'jelly': """✨ DESCRIPCIÓN
  • Ayuda a controlar el peso corporal
  • Reduce la sensación de hambre
  • Promueve la digestión saludable

🌿 INGREDIENTES CLAVE
  • Extracto de Garcinia Cambogia
  • Fibra de granada y chía
  • Maltodextrina resistente

📋 MODO DE USO
  • Consumir antes de las comidas principales
  • Acompañar con suficiente agua"""
    }
    
    # Buscar coincidencia por tipo de producto
    for key, desc in descripciones_genericas.items():
        if key in nombre_lower:
            return desc
    
    # Descripción genérica por defecto
    return f"""✨ {nombre[:60]}

🌟 CARACTERÍSTICAS
  • Producto original de Corea del Sur
  • Formulado con ingredientes de alta calidad
  • Tecnología avanzada de belleza coreana

📋 MODO DE USO
  • Sigue las instrucciones del empaque
  • Para mejores resultados, usa consistentemente"""

def scrape_product(url, traductor, intento=1):
    print(f"  📦 Procesando...", end="")
    
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
            
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    html = content.decode(encoding)
                    break
                except:
                    continue
            
            product = extract_product_info(html, url, traductor)
            print(f" ✅ {product['name'][:40]}...")
            return product
            
    except Exception as e:
        print(f" ❌ Error: {str(e)[:50]}")
        if intento < MAX_INTENTOS:
            print(f"     🔄 Reintentando ({intento+1}/{MAX_INTENTOS})...")
            time.sleep(2)
            return scrape_product(url, traductor, intento+1)
        
        return {
            "name": "Error al cargar producto",
            "price_usd": None,
            "price_crc": None,
            "description": "Producto temporalmente no disponible. Consulte disponibilidad.",
            "imageUrl": None,
        }

def cargar_urls():
    try:
        with open('Productos_urls.txt', 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and line.startswith('http')]
        print(f"✅ Cargadas {len(urls)} URLs desde Productos_urls.txt")
        return urls
    except FileNotFoundError:
        print("⚠️ No se encontró Productos_urls.txt, usando URLs de ejemplo")
        return [
            "https://www.stylekorean.com/shop/foodology-renewal-coleology-cutting-jelly-10-pouch/1768386373/",
        ]

# ==================== GENERACIÓN DEL CATÁLOGO ====================
def generar_html_catalogo(products):
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    html_template = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title> My Beauty Store - Catálogo de Productos</title>
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
        
        .price-container { 
            margin: 15px 0 20px 0;
        }
        
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
        
        .product-description strong {
            color: #2c3e50;
        }
        
        .add-to-cart { 
            align-self: flex-start;
            margin-top: 10px;
            padding: 12px 30px; 
            background: linear-gradient(135deg, #27ae60, #2ecc71); 
            color: white; 
            border: none; 
            border-radius: 50px; 
            font-size: 16px; 
            font-weight: 700; 
            cursor: pointer; 
            transition: transform 0.3s;
        }
        
        .add-to-cart:hover { 
            transform: translateY(-2px); 
            box-shadow: 0 5px 20px rgba(46, 204, 113, 0.4);
        }
        
        .stats { 
            text-align: center; 
            color: white; 
            margin: 30px auto; 
            padding: 30px; 
            background: rgba(0,0,0,0.1); 
            border-radius: 15px; 
            max-width: 800px; 
        }
        
        .whatsapp-btn { 
            position: fixed; 
            bottom: 30px; 
            right: 30px; 
            background: #25D366; 
            color: white; 
            padding: 15px 20px; 
            border-radius: 50px; 
            text-decoration: none; 
            font-weight: bold; 
            display: flex; 
            align-items: center; 
            gap: 10px; 
            z-index: 100; 
            transition: transform 0.3s; 
        }
        
        .whatsapp-btn:hover { transform: scale(1.05); }
        
        @keyframes fadeIn { 
            from { opacity: 0; transform: translateY(30px); } 
            to { opacity: 1; transform: translateY(0); } 
        }
        
        @media (max-width: 768px) { 
            .product-card { 
                flex-direction: column;
            }
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
        <h1>✨ My Beauty Store ✨</h1>
        <p>Lo mejor de la cosmética coreana en Costa Rica</p>
        <div class="stats-badge">📊 {product_count} productos disponibles</div>
        <p style="font-size: 12px; margin-top: 10px;">Actualizado: {fecha}</p>
    </div>
    
    <div class="catalog">{product_cards}</div>
    
    <div class="stats">
        <p>🌟 Productos 100% originales de Corea del Sur</p>
        <p>🚚 Envíos a todo Costa Rica (3-5 días hábiles)</p>
        <p>💳 Aceptamos transferencia, SINPE y efectivo contra entrega</p>
    </div>
    
    <a href="https://wa.me/506XXXXXXXX?text=Hola%21%20Vi%20el%20cat%C3%A1logo%20de%20MyBeautyStore%20y%20me%20interesa%20hacer%20un%20pedido" class="whatsapp-btn" target="_blank">💬 ¡Pide por WhatsApp!</a>
    
    <script>
        function agregarAlCarrito(nombreProducto, precio) {
            alert(`✨ ¡${nombreProducto} ha sido agregado al carrito!\\n\\n💰 Precio: ${precio}\\n\\n📞 Un asesor se comunicará contigo para confirmar tu pedido.`);
        }
    </script>
</body>
</html>'''
    
    product_cards = []
    for product in products:
        image_url = product.get('imageUrl', 'https://via.placeholder.com/300x300?text=MyBeautyStore ')
        precio_formateado = format_price_crc(product.get('price_crc'))
        nombre_limpio = product['name'].replace("'", "\\'").replace('"', '&quot;')
        
        # Convertir saltos de línea de la descripción a <br> para HTML
        descripcion_html = product.get('description', '')
        descripcion_html = descripcion_html.replace('\n', '<br>')
        
        card = f'''
        <div class="product-card">
            <div class="product-image-container">
                <img class="product-image" src="{image_url}" alt="{escape(product['name'])}" loading="lazy" onerror="this.src='https://via.placeholder.com/300x300?text=MyBeautyStore'">
            </div>
            <div class="product-info">
                <div class="product-name">{escape(product['name'])}</div>
                <div class="price-container">
                    <span class="product-price">{precio_formateado}</span>
                </div>
                <div class="product-description">{descripcion_html}</div>
                <button class="add-to-cart" onclick="agregarAlCarrito('{nombre_limpio}', '{precio_formateado}')">🛒 Agregar al carrito</button>
            </div>
        </div>'''
        product_cards.append(card)
    
    final_html = html_template.replace('{product_cards}', '\n'.join(product_cards))
    final_html = final_html.replace('{product_count}', str(len(products)))
    final_html = final_html.replace('{fecha}', fecha_actual)
    
    return final_html

# ==================== MAIN ====================
def main():
    print("\n" + "="*50)
    print("🚀 INICIANDO GENERACIÓN DE CATÁLOGO")
    print("="*50)
    print(f"💰 Tasa de cambio: 1 USD = {USD_TO_CRC} CRC")
    print(f"📈 Marcups: $10-27→45% | $27-38→30% | >$38→20%")
    print(f"🌐 Búsqueda en internet: Activada (DuckDuckGo + Olivia)")
    print("✨ DESCRIPCIONES FORMATEADAS: Activado (secciones con viñetas)")
    print("="*50)
    
    urls = cargar_urls()
    total_productos = len(urls)
    print(f"\n📊 Total productos a procesar: {total_productos}")
    
    if total_productos == 0:
        print("❌ No hay URLs para procesar")
        return
    
    print("\n🔧 Inicializando traductor...")
    traductor = TraductorIlimitado()
    
    productos_procesados = []
    tiempo_inicio = time.time()
    
    for idx, url in enumerate(urls, 1):
        print(f"\n📦 [{idx}/{total_productos}]")
        producto = scrape_product(url, traductor)
        productos_procesados.append(producto)
        
        if idx % TAMANO_LOTE == 0:
            with open(f"progreso_{idx}.json", "w", encoding="utf-8") as f:
                json.dump(productos_procesados, f, indent=2, ensure_ascii=False)
            print(f"  💾 Progreso guardado")
        
        time.sleep(TIEMPO_ENTRE_PETICIONES)
    
    tiempo_total = time.time() - tiempo_inicio
    print("\n" + "="*50)
    print("📊 ESTADÍSTICAS DEL PROCESO")
    print("="*50)
    print(f"⏱️ Tiempo total: {tiempo_total:.1f} segundos")
    print(f"📦 Productos: {len(productos_procesados)}")
    print(f"⚡ Promedio: {tiempo_total/len(productos_procesados):.1f} seg/producto")
    
    traductor.mostrar_estadisticas()
    
    print("\n🎨 Generando catálogo HTML con descripciones formateadas...")
    html_content = generar_html_catalogo(productos_procesados)
    
    output_file = "Catalogo_2026.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    with open("Productos.json", "w", encoding="utf-8") as f:
        json.dump(productos_procesados, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ ¡COMPLETADO!")
    print(f"📁 HTML: {output_file}")
    print("\n🎉 ¡Listo! Abre el archivo HTML en tu navegador.")
    print("\n✨ Las descripciones ahora se muestran con secciones organizadas y viñetas ✨")

if __name__ == "__main__":
    main()
    input("\nPresiona Enter para salir...")