"""Nucleo del buscador: configura, consulta las fuentes, filtra, guarda y reporta.

Este modulo contiene la logica principal del sistema. La aplicacion de escritorio
(app.pyw) y los scripts de terminal (eliminar.py, verificar.py) importan sus
funciones; la tarea programada de Windows ejecuta main() directamente.
"""
import csv
import html
import json
import os
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fuentes import computrabajo, findjob24h, linkedin, trabajo_org
from fuentes.comun import sin_acentos
from notificar import enviar_correo, toast

# ---------- Rutas de los archivos de datos ----------
DATA = os.path.join(BASE, "data")
CONFIG_PATH = os.path.join(BASE, "config.json")
EJEMPLO_CONFIG_PATH = os.path.join(BASE, "config.example.json")
VISTAS_PATH = os.path.join(DATA, "vistas.json")
OFERTAS_PATH = os.path.join(DATA, "ofertas.csv")
REPORTE_PATH = os.path.join(DATA, "reporte.html")
LOG_PATH = os.path.join(DATA, "historial.log")
NEGRA_PATH = os.path.join(DATA, "lista_negra.json")

# ---------- Valores por defecto (se usan si falta alguna clave en config.json) ----------
FUERTES = [
    "soporte", "support", "helpdesk", "help desk", "mesa de ayuda", "redes", "network",
    "informatic", "sistemas", "infraestructura", "ciberseguridad", "sysadmin",
    "service desk", "telecom", "servidor", "cableado", "m365", "active directory",
    "windows", "desktop", "endpoint", "data center",
]
EXCLUIR = ["redes sociales", "community manager", "calidad", "vendedor", "ventas"]
REMOTO = ["remoto", "teletrabajo", "hibrido", "remote", "home office", "desde casa", "work from home"]
FUENTES = [computrabajo, trabajo_org, findjob24h, linkedin]
COLUMNAS = ["fecha", "fuente", "titulo", "ubicacion", "empresa", "url", "estado_envio"]


DEFECTO_CONFIG = {
    "palabras_clave_busqueda": ["soporte ti", "soporte tecnico", "redes", "help desk"],
    "palabras_clave": ["soporte", "redes", "network", "helpdesk", "sistemas"],
    "palabras_excluidas": ["ventas", "comercial", "marketing", "contabilidad"],
    "palabras_remoto": ["remoto", "teletrabajo", "remote", "hibrido"],
    "zonas": ["alajuela", "san jose"],
    "incluir_remoto": True,
}


# ---------- Configuracion ----------
def asegurar_config():
    """Crea config.json la primera vez (copiando config.example.json o usando DEFECTO_CONFIG)."""
    if os.path.exists(CONFIG_PATH):
        return
    if os.path.exists(EJEMPLO_CONFIG_PATH):
        with open(EJEMPLO_CONFIG_PATH, encoding="utf-8") as e:
            datos = json.load(e)
    else:
        datos = DEFECTO_CONFIG
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def cargar_config():
    """Lee config.json (creandolo si no existe) y lo devuelve como diccionario."""
    asegurar_config()
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------- Lectura y escritura de datos ----------
def cargar_vistas():
    """Devuelve {clave_url: fecha} de las ofertas ya vistas; dict vacio si el archivo falta o falla."""
    if not os.path.exists(VISTAS_PATH):
        return {}
    try:
        with open(VISTAS_PATH, encoding="utf-8") as f:
            datos = json.load(f)
        return datos.get("urls", datos) if isinstance(datos, dict) else {}
    except Exception:
        return {}


def guardar_vistas(vistas):
    """Guarda el diccionario de ofertas vistas en vistas.json."""
    with open(VISTAS_PATH, "w", encoding="utf-8") as f:
        json.dump({"urls": vistas}, f, ensure_ascii=False, indent=1)


def cargar_ofertas():
    """Lee ofertas.csv (separador ';') y devuelve la lista de filas como diccionarios."""
    if not os.path.exists(OFERTAS_PATH):
        return []
    with open(OFERTAS_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def clave_url(url):
    """Normaliza una URL para usarla como clave: sin #final, sin espacios y en minusculas."""
    return url.split("#", 1)[0].strip().lower()


def guardar_ofertas(ofertas):
    """Reescribe ofertas.csv completo con la lista de ofertas dada."""
    with open(OFERTAS_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";")
        w.writeheader()
        w.writerows(ofertas)


def cargar_lista_negra():
    """Lee lista_negra.json migrando al formato {hasta, titulo, fuente} si estaba en el formato viejo."""
    if not os.path.exists(NEGRA_PATH):
        return {}
    try:
        with open(NEGRA_PATH, encoding="utf-8") as f:
            datos = json.load(f)
        urls = datos.get("urls", datos) if isinstance(datos, dict) else {}
    except Exception:
        return {}
    salida = {}
    cambiado = False
    for k, v in urls.items():
        if isinstance(v, dict) and "hasta" in v:
            salida[k] = v
        else:
            salida[k] = {"hasta": v if isinstance(v, str) else "", "titulo": "", "fuente": ""}
            cambiado = True
    if cambiado:
        guardar_lista_negra(salida)
    return salida


def guardar_lista_negra(negra):
    """Guarda TODO el diccionario de la lista negra (sobrescribe el archivo: hacer merge antes)."""
    with open(NEGRA_PATH, "w", encoding="utf-8") as f:
        json.dump({"urls": negra}, f, ensure_ascii=False, indent=1)


def purgar_lista_negra():
    """Elimina de la lista negra las entradas cuya fecha 'hasta' ya paso y devuelve las vivas."""
    negra = cargar_lista_negra()
    hoy = datetime.now().strftime("%Y-%m-%d")
    vivas = {k: v for k, v in negra.items() if (v.get("hasta") or "") >= hoy}
    if len(vivas) != len(negra):
        guardar_lista_negra(vivas)
    return vivas


# ---------- Eliminaciones y lista negra ----------
def dias_lista_negra():
    """Devuelve cuantos dias dura la lista negra (clave del config, defecto 15)."""
    try:
        return int(cargar_config().get("dias_lista_negra", 15))
    except Exception:
        return 15


def pasar_a_lista_negra(items):
    """Pone URLs en lista negra con titulo y fuente. items: dicts con url, titulo, fuente.

    Devuelve la fecha de expiracion (YYYY-MM-DD) o None si no habia URLs.
    """
    claves = {clave_url(i.get("url", "")) for i in items if i.get("url")}
    if not claves:
        return None
    info = {clave_url(i.get("url", "")): i for i in items}
    vistas = cargar_vistas()
    quitadas = [k for k in vistas if k in claves]
    for k in quitadas:
        vistas.pop(k)
    if quitadas:
        guardar_vistas(vistas)
    negra = purgar_lista_negra()
    expira = (datetime.now() + timedelta(days=dias_lista_negra())).strftime("%Y-%m-%d")
    for k in claves:
        i = info.get(k, {})
        negra[k] = {
            "hasta": expira,
            "titulo": i.get("titulo", ""),
            "fuente": i.get("fuente", ""),
        }
    guardar_lista_negra(negra)
    return expira


def purgar_ofertas(dias):
    """Borra del CSV las ofertas con mas de N dias (las marcadas con estado se conservan).

    Las borradas pasan a la lista negra. Devuelve (total_antes, cuantas_borradas).
    """
    if not dias or not os.path.exists(OFERTAS_PATH):
        return 0, 0
    ofertas = cargar_ofertas()
    if not ofertas:
        return 0, 0
    limite = (datetime.now() - timedelta(days=int(dias))).strftime("%Y-%m-%d")
    conservadas = []
    borradas = 0
    items = []
    for o in ofertas:
        fecha = (o.get("fecha") or "").strip()
        marcada = (o.get("estado_envio") or "").strip()
        if fecha and fecha < limite and not marcada:
            borradas += 1
            items.append({"url": o.get("url", ""), "titulo": o.get("titulo", ""), "fuente": o.get("fuente", "")})
        else:
            conservadas.append(o)
    if borradas:
        guardar_ofertas(conservadas)
        expira = pasar_a_lista_negra(items)
        registrar(f"PURGA dias={dias} borradas={borradas} negra_hasta={expira}")
    return len(ofertas), borradas


def eliminar_ofertas(urls):
    """Elimina del CSV las ofertas indicadas y las pasa a la lista negra. Devuelve cuantas borró."""
    claves = {clave_url(u) for u in urls if u}
    if not claves:
        return 0
    ofertas = cargar_ofertas()
    items = [
        {"url": o.get("url", ""), "titulo": o.get("titulo", ""), "fuente": o.get("fuente", "")}
        for o in ofertas
        if clave_url(o.get("url", "")) in claves
    ]
    restantes = [o for o in ofertas if clave_url(o.get("url", "")) not in claves]
    borradas = len(ofertas) - len(restantes)
    if borradas:
        guardar_ofertas(restantes)
    expira = pasar_a_lista_negra(items)
    registrar(f"ELIMINADO urls={len(claves)} filas={borradas} negra_hasta={expira}")
    return borradas


# ---------- Reporte y registro ----------
def refrescar_reporte(borradas=0):
    """Regenera reporte.html con los datos actuales; los errores solo se anotan en el log."""
    try:
        cfg = cargar_config()
        todas = cargar_ofertas()
        hoy = datetime.now().strftime("%Y-%m-%d")
        nuevas = [o for o in todas if (o.get("fecha") or "") == hoy]
        escribir_reporte(
            nuevas,
            todas,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            int(cfg.get("dias_retencion", 15)),
            borradas,
        )
    except Exception as e:
        registrar(f"aviso refrescar reporte {type(e).__name__}")


def pasa_filtros(oferta, zonas, cfg):
    """Decide si una oferta cruda entra al CSV.

    Reglas: nada de palabras excluidas; al menos una palabra clave tecnica
    (o "tecnico" + area de TI); y zona aceptada, remoto permitido, o la fuente
    Trabajo.org (que ya trae las zonas en su busqueda).
    """
    texto = sin_acentos(f"{oferta['titulo']} {oferta['ubicacion']}")
    excluidas = [sin_acentos(x) for x in cfg.get("palabras_excluidas", EXCLUIR)]
    if any(x in texto for x in excluidas):
        return False
    claves = [sin_acentos(k) for k in cfg.get("palabras_clave", FUERTES)]
    tiene_fuerte = any(k in texto for k in claves)
    tiene_tecnico = "tecnico" in texto and any(k in texto for k in ("informatic", "comput", "soporte", "redes", "sistemas"))
    if not (tiene_fuerte or tiene_tecnico):
        return False
    zona_ok = any(z in texto for z in zonas)
    remotos = [sin_acentos(r) for r in cfg.get("palabras_remoto", REMOTO)]
    remoto_ok = cfg.get("incluir_remoto", True) and any(r in texto for r in remotos)
    return zona_ok or remoto_ok or oferta["fuente"] == "Trabajo.org"


def recolectar(cfg):
    """Consulta las 4 fuentes y junta sus ofertas; una fuente que falle no detiene el resto."""
    todas = []
    for modulo in FUENTES:
        try:
            todas.extend(modulo.buscar(cfg))
        except Exception as e:
            print(f"  aviso: {modulo.__name__} falló ({type(e).__name__})")
    return todas


def escribir_csv(nuevas):
    """Agrega las ofertas nuevas al final de ofertas.csv (crea el archivo con encabezado si falta)."""
    existe = os.path.exists(OFERTAS_PATH)
    with open(OFERTAS_PATH, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";")
        if not existe:
            w.writeheader()
        for o in nuevas:
            w.writerow(o)


def escribir_reporte(nuevas, todas, generado, dias_retencion, borradas):
    """Genera reporte.html de solo lectura con las ofertas de hoy y el acumulado."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    try:
        dias_negra = int(cargar_config().get("dias_lista_negra", 15))
    except Exception:
        dias_negra = 15

    def dias_de(fecha):
        """Dias transcurridos desde la fecha de la oferta hasta hoy (o '-')."""
        try:
            d = (datetime.strptime(hoy, "%Y-%m-%d") - datetime.strptime(fecha, "%Y-%m-%d")).days
            return str(d)
        except Exception:
            return "-"

    def filas(items):
        """Convierte las ofertas en filas <tr> de tabla HTML con el texto escapado."""
        out = []
        for o in items:
            url = html.escape(o.get("url", ""), quote=True)
            out.append(
                "<tr>"
                f"<td>{html.escape(o.get('fecha', ''))}</td>"
                f"<td>{html.escape(o.get('fuente', ''))}</td>"
                f"<td><a href=\"{url}\" target=\"_blank\">{html.escape(o.get('titulo', ''))}</a></td>"
                f"<td>{html.escape(o.get('ubicacion', ''))}</td>"
                f"<td>{dias_de(o.get('fecha', ''))}</td>"
                f"<td>{html.escape(o.get('estado_envio', ''))}</td>"
                "</tr>"
            )
        return "\n".join(out)

    cuerpo = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Buscador de Puestos - Reporte</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #222; }}
h1 {{ color: #1a5276; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 28px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 14px; text-align: left; }}
th {{ background: #1a5276; color: #fff; }}
tr:nth-child(even) {{ background: #eaf2f8; }}
.nuevas tr {{ background: #d4efdf; }}
.nota {{ background: #fef9e7; border: 1px solid #f9e79f; padding: 10px 14px; font-size: 13px; }}
</style></head><body>
<h1>Buscador de Puestos</h1>
<p>Generado: {html.escape(generado)} | Ofertas nuevas: {len(nuevas)} | Total acumulado: {len(todas)} | Purgadas hoy: {borradas}</p>
<p class="nota">Visor de solo lectura. Para eliminar ofertas (lista negra de {dias_negra} dias),
marcar estados o buscar, usa la aplicacion: doble clic en <b>Abrir Ofertas</b>.
Las ofertas con mas de {int(dias_retencion)} dias se retiran solas.</p>
<h2>Nuevas de hoy</h2>
<table class="nuevas"><tr><th>Fecha</th><th>Fuente</th><th>Puesto</th><th>Ubicacion</th><th>Dias</th><th>Estado</th></tr>
{filas(nuevas)}
</table>
<h2>Todas las coincidencias</h2>
<table><tr><th>Fecha</th><th>Fuente</th><th>Puesto</th><th>Ubicacion</th><th>Dias</th><th>Estado</th></tr>
{filas(todas)}
</table>
</body></html>"""
    with open(REPORTE_PATH, "w", encoding="utf-8") as f:
        f.write(cuerpo)


def registrar(mensaje):
    """Agrega una linea con fecha y hora a data/historial.log (crea la carpeta si falta)."""
    os.makedirs(DATA, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {mensaje}\n")


# ---------- Ejecucion principal ----------
def main():
    """Corre una busqueda completa: purga, consulta, filtra, guarda, verifica y reporta.

    Orden: (1) purga por antiguedad, (2) recolectar de las 4 fuentes,
    (3) filtrar por perfil, (4) descartar vistas/negra y guardar nuevas,
    (5) verificar ofertas cerradas, (6) reporte, vistas, avisos y log.
    """
    os.makedirs(DATA, exist_ok=True)
    cfg = cargar_config()
    zonas = [sin_acentos(z) for z in cfg.get("zonas", [])]
    dias_retencion = int(cfg.get("dias_retencion", 15))
    _, borradas = purgar_ofertas(dias_retencion)
    if borradas:
        print(f"  purgadas (>{dias_retencion} dias): {borradas}")
    print("Buscando ofertas...")
    crudas = recolectar(cfg)
    print(f"  crudas: {len(crudas)}")
    filtradas = [o for o in crudas if pasa_filtros(o, zonas, cfg)]
    print(f"  coinciden: {len(filtradas)}")
    vistas = cargar_vistas()
    negra = purgar_lista_negra()
    previas = {clave_url(o["url"]) for o in cargar_ofertas()}
    hoy = datetime.now().strftime("%Y-%m-%d")
    nuevas = []
    for o in filtradas:
        clave = clave_url(o["url"])
        if clave in negra or clave in vistas or clave in previas:
            continue
        vistas[clave] = hoy
        nuevas.append(
            {
                "fecha": hoy,
                "fuente": o["fuente"],
                "titulo": o["titulo"],
                "ubicacion": o["ubicacion"],
                "empresa": o.get("empresa", ""),
                "url": o["url"],
                "estado_envio": "",
            }
        )
    escribir_csv(nuevas)
    cerradas = 0
    if cfg.get("verificar_en_busqueda", True):
        try:
            from verificar import verificar_ofertas

            retiradas, revisadas = verificar_ofertas(cfg)
            cerradas = len(retiradas)
            if retiradas:
                print(f"  ofertas cerradas retiradas: {cerradas} (revisadas {revisadas})")
        except Exception as e:
            print(f"  aviso: verificación falló ({type(e).__name__})")
    todas = cargar_ofertas()
    generado = datetime.now().strftime("%Y-%m-%d %H:%M")
    escribir_reporte(nuevas, todas, generado, dias_retencion, borradas)
    guardar_vistas(vistas)
    print(f"  nuevas: {len(nuevas)} | acumuladas: {len(todas)}")
    for o in nuevas:
        print(f"   + [{o['fuente']}] {o['titulo']} ({o['ubicacion']})")
    print(f"Reporte: {REPORTE_PATH}")
    if nuevas and cfg.get("notificar_toast", True):
        titulo = "Buscador de Puestos"
        mensaje = f"{len(nuevas)} oferta(s) nueva(s). Revisa postulaciones/ofertas.csv"
        toast(titulo, mensaje)
    if nuevas:
        try:
            enviar_correo(cfg.get("correo", {}), f"{len(nuevas)} ofertas nuevas", f"<p>Revisa el reporte en {REPORTE_PATH}</p>")
        except Exception as e:
            print(f"  aviso: correo falló ({type(e).__name__})")
    registrar(f"OK crudas={len(crudas)} coinciden={len(filtradas)} nuevas={len(nuevas)} borradas={borradas} cerradas={cerradas} acumuladas={len(todas)}")
    if cfg.get("abrir_reporte") and nuevas:
        os.startfile(REPORTE_PATH)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        registrar("ERROR " + traceback.format_exc().replace("\n", " | "))
        raise
