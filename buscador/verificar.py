import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fuentes.comun import CTX, UA, pausar
from main import cargar_config, cargar_ofertas, eliminar_ofertas, registrar

MARCAS_CIERRE = [
    "ya no se acepta",
    "no se aceptan solicitudes",
    "la oferta ha sido cerrada",
    "oferta cerrada",
    "oferta finalizada",
    "esta oferta ya no",
    "ya no esta disponible",
    "esta oferta no existe",
    "no longer accepting",
    "job has expired",
    "this job has expired",
    "job not found",
    "position has been filled",
    "job has been filled",
    "application period has ended",
]


def obtener(url, timeout=25):
    """Devuelve (codigo, url_final, html). Lanza HTTPError en 4xx/5xx."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, r.geturl(), r.read().decode("utf-8", "replace")


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).lower()


def _validthrough(html):
    m = re.search(r'"?validthrough"?\s*[:=]\s*"([^"]+)"', html, re.I)
    if not m:
        return None
    m2 = re.match(r"(\d{4}-\d{2}-\d{2})", m.group(1))
    return m2.group(1) if m2 else None


def _id_computrabajo(url):
    ultimo = url.rstrip("/").rsplit("-", 1)[-1]
    return ultimo if re.fullmatch(r"[0-9A-Fa-f]{16,}", ultimo) else None


def estado_oferta(oferta, obtener_fn=obtener):
    """'viva' | 'cerrada' | 'desconocida'. Solo evidencia positiva borra."""
    url = oferta.get("url", "")
    fuente = oferta.get("fuente", "")
    try:
        _, final, html = obtener_fn(url)
    except urllib.error.HTTPError as e:
        return "cerrada" if e.code in (404, 410) else "desconocida"
    except Exception:
        return "desconocida"
    if len(html) < 2000:
        return "desconocida"
    texto = _texto(html)
    if any(m in texto for m in MARCAS_CIERRE):
        return "cerrada"
    vt = _validthrough(html)
    if vt and vt < datetime.now().strftime("%Y-%m-%d"):
        return "cerrada"
    if fuente == "Computrabajo":
        ident = _id_computrabajo(url)
        if ident and ident.lower() not in final.lower() and ident.lower() not in html.lower():
            return "cerrada"
    return "viva"


def verificar_ofertas(cfg=None, obtener_fn=obtener):
    """Revisa ofertas anteriores a hoy y retira las cerradas. Devuelve (retiradas, revisadas)."""
    if cfg is None:
        cfg = cargar_config()
    hoy = datetime.now().strftime("%Y-%m-%d")
    maximo = int(cfg.get("verificar_max_por_corrida", 30))
    pausa = max(cfg.get("pausa_segundos", 0.7), 0.8)
    candidatas = sorted(
        (o for o in cargar_ofertas() if (o.get("fecha") or "") < hoy),
        key=lambda o: o.get("fecha", ""),
    )[:maximo]
    retiradas = []
    revisadas = 0
    for o in candidatas:
        revisadas += 1
        if estado_oferta(o, obtener_fn) == "cerrada":
            retiradas.append(o)
        pausar(pausa)
    if retiradas:
        eliminar_ofertas([o.get("url", "") for o in retiradas])
        detalle = "; ".join(f"{o.get('titulo', '')[:40]} ({o.get('fuente', '')})" for o in retiradas)
        registrar(f"VERIFICACION cerradas={len(retiradas)} revisadas={revisadas}: {detalle}")
    return retiradas, revisadas


if __name__ == "__main__":
    try:
        cfg = cargar_config()
        retiradas, revisadas = verificar_ofertas(cfg)
        print(f"Revisadas: {revisadas} | cerradas retiradas: {len(retiradas)}")
        for o in retiradas:
            print(f"  - {o.get('titulo', '')} ({o.get('fuente', '')})")
        if retiradas and cfg.get("notificar_toast", True):
            from notificar import toast

            toast("Buscador de Puestos", f"{len(retiradas)} oferta(s) ya no disponibles retiradas")
    except Exception:
        import traceback

        registrar("ERROR verificar " + traceback.format_exc().replace("\n", " | "))
        raise
