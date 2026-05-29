import os
import re
import requests
from urllib.parse import urljoin

BASE_DIR = "Cartas"
MENU_URL = "https://www.caica.ru/ANI_Official/Aip/html/menueng.htm"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def get_rusia_icaos():
    """Obtiene todos los ICAOs rusos desde el menú HTML."""
    resp = requests.get(MENU_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text
    
    patron = r'ItemBegin\("[^"]*",\s*"[^"]*",\s*"([A-Z]{4})\. [^"]+"\)'
    matches = re.findall(patron, html)
    icaos = list(dict.fromkeys(matches))
    icaos.sort()
    return icaos


# ----------------------------------------------------------------------
# 1. Obtener las cartas desde el menú de Rusia
# ----------------------------------------------------------------------
def obtener_cartas_rusia(icao):
    print(f"  Descargando menú de Rusia...")
    resp = requests.get(MENU_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    icao_upper = icao.upper()
    patron_begin = rf'ItemBegin\("[^"]*",\s*"[^"]*",\s*"{icao_upper}\. [^"]+"\)'
    match_begin = re.search(patron_begin, html)

    if not match_begin:
        print(f"  No se encontró el aeropuerto {icao} en el menú de Rusia.")
        return []

    pos_inicio = match_begin.end()
    match_end = re.search(r'ItemEnd\(\);', html[pos_inicio:])
    if not match_end:
        print("  No se encontró el cierre del bloque ItemEnd.")
        return []

    bloque = html[pos_inicio:pos_inicio + match_end.start()]

    patron_link = r'ItemLink\("([^"]+)","([^"]+)"\)'
    enlaces = re.findall(patron_link, bloque)

    cartas = []
    for url_rel, descripcion in enlaces:
        url_completa = urljoin(MENU_URL, url_rel)
        cartas.append((descripcion.strip(), url_completa))

    return cartas

# ----------------------------------------------------------------------
# 2. Clasificar carta según su descripción
# ----------------------------------------------------------------------
def clasificar_carta_rusia(descripcion):
    desc_upper = descripcion.upper()

    # SID
    if 'SID' in desc_upper or 'STANDARD DEPARTURE' in desc_upper or 'STANDARD VISUAL DEPARTURE' in desc_upper:
        return "SID"

    # STAR
    if 'STAR' in desc_upper or 'STANDARD ARRIVAL' in desc_upper or 'STANDARD VISUAL ARRIVAL' in desc_upper:
        return "STAR"

    # APP (aproximaciones)
    if any(p in desc_upper for p in [
        'INSTRUMENT APPROACH', 'ILS', 'GLS', 'RNP', 'NDB', 'VOR',
        'APPROACH CHART', 'RNAV'
    ]):
        return "APP"

    # GRND (cartas de aeródromo)
    if any(p in desc_upper for p in [
        'AERODROME CHART', 'GROUND MOVEMENT', 'OBSTACLE CHART',
        'AREA CHART', 'ATC SURVEILLANCE', 'COORDINATES',
        'DATA, TEXTS, TABLES', 'AERODROME OBSTACLE', 'PARKING'
    ]):
        return "GRND"

    return "GENERAL"


def scrape_cartas_rusia(icao):
    """Scrapea todas las cartas de un aeropuerto ruso. Retorna lista de dicts."""
    if not re.match(r'^[A-Z]{4}$', icao):
        return []
    
    cartas_tuplas = obtener_cartas_rusia(icao)
    cartas = []
    for descripcion, url in cartas_tuplas:
        tipo = clasificar_carta_rusia(descripcion)
        cartas.append({
            'descripcion': descripcion,
            'tipo': tipo,
            'url': url
        })
    return cartas


# ----------------------------------------------------------------------
# 3. Descargar y guardar las cartas
# ----------------------------------------------------------------------
def descargar_rusia(icao, tipo_filtro=None):
    if not re.match(r'^[A-Z]{4}$', icao):
        print("Código ICAO inválido. Debe tener 4 letras (ej. UNAA, URKA).")
        return

    cartas = obtener_cartas_rusia(icao)
    if not cartas:
        print(f"No se encontraron cartas para {icao}.")
        return

    print(f"Se encontraron {len(cartas)} cartas para {icao}.")

    carpeta_destino = os.path.join(BASE_DIR, "Rusia", icao)
    os.makedirs(carpeta_destino, exist_ok=True)

    cartas_guardadas = 0
    for descripcion, url in cartas:
        nombre_archivo = re.sub(r'[<>:"/\\|?*°]', '', descripcion) + ".pdf"
        ruta_temporal = os.path.join(carpeta_destino, nombre_archivo)

        if not os.path.exists(ruta_temporal):
            print(f"  Descargando: {nombre_archivo}")
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                with open(ruta_temporal, "wb") as f:
                    f.write(resp.content)
            except Exception as e:
                print(f"    Error al descargar: {e}")
                continue
        else:
            print(f"  Ya existe: {nombre_archivo}")

        tipo = clasificar_carta_rusia(descripcion)
        if tipo_filtro and tipo != tipo_filtro:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
            continue

        carpeta_tipo = os.path.join(carpeta_destino, tipo)
        os.makedirs(carpeta_tipo, exist_ok=True)
        ruta_final = os.path.join(carpeta_tipo, nombre_archivo)

        if os.path.exists(ruta_final):
            base, ext = os.path.splitext(nombre_archivo)
            contador = 1
            while True:
                nuevo_nombre = f"{base}_{contador}{ext}"
                ruta_final = os.path.join(carpeta_tipo, nuevo_nombre)
                if not os.path.exists(ruta_final):
                    break
                contador += 1

        try:
            os.rename(ruta_temporal, ruta_final)
            print(f"    → [{tipo}] {nombre_archivo}")
            cartas_guardadas += 1
        except Exception as e:
            print(f"    Error al mover: {e}")

    if tipo_filtro and cartas_guardadas == 0:
        print(f"\nEste aeropuerto no posee cartas de tipo {tipo_filtro}.")
    else:
        print(f"Proceso completado. {cartas_guardadas} cartas guardadas en {carpeta_destino}")

# ----------------------------------------------------------------------
# Prueba independiente
# ----------------------------------------------------------------------
if __name__ == "__main__":
    icao = input("Código ICAO (ej. UNAA, URKA): ").strip().upper()
    print("\nSeleccione el tipo de cartas a descargar:")
    print("1. Todas")
    print("2. Solo SID")
    print("3. Solo STAR")
    print("4. Solo APP")
    print("5. Solo GRND")
    print("6. Solo GENERAL")
    tipo_opcion = input("Opción: ").strip()
    tipo_filtro = None
    if tipo_opcion == '2': tipo_filtro = "SID"
    elif tipo_opcion == '3': tipo_filtro = "STAR"
    elif tipo_opcion == '4': tipo_filtro = "APP"
    elif tipo_opcion == '5': tipo_filtro = "GRND"
    elif tipo_opcion == '6': tipo_filtro = "GENERAL"
    descargar_rusia(icao, tipo_filtro)