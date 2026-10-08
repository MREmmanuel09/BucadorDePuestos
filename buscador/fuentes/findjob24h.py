"""Buscador de ofertas en cr.findjob24h.com con verificacion de detalle."""

import re
from urllib.parse import urljoin

from .comun import fetch, pausar, sin_acentos

BASE = "https://cr.findjob24h.com"
PATRON_LISTA = re.compile(r'href="([^"]*-job\d+)"')
PATRON_UBICACION = re.compile(
    r"Ubicaci[oó]n[:\s]+(.{3,80}?)(?=\s(?:Categor|Industria|Posici|Tipo|Plazo|D[ií]a|Ver:|Requis|Funciones|Salario|Correo|Email)|$)"
)

FUERTES = [
    "soporte",
    "helpdesk",
    "help-desk",
    "help desk",
    "redes",
    "network",
    "informatic",
    "sistemas",
    "infraestructura",
    "ciberseguridad",
    "sysadmin",
    "service desk",
    "telecom",
    "servidor",
    "cableado",
]


def _candidata(slug):
    """Indica si el enlace parece ser de un puesto informatico (sin acentos)."""
    texto = sin_acentos(slug)
    return any(k in texto for k in FUERTES)


def _titulo_desde_slug(rel):
    """Construye el titulo de la oferta a partir del ultimo tramo de la URL."""
    parte = rel.split("/")[-1]
    parte = re.sub(r"-job\d+$", "", parte)
    return parte.replace("-", " ").title()


def buscar(cfg):
    """Busca ofertas de TI en FindJob24h y verifica el detalle de las primeras."""
    ofertas = []
    pausa = cfg.get("pausa_segundos", 0.7)
    limite = int(cfg.get("max_detalles_findjob24h", 25))
    candidatos = []
    vistos = set()
    try:
        html = fetch(BASE + "/")
    except Exception:
        return []
    for rel in PATRON_LISTA.findall(html):
        if rel in vistos:
            continue
        vistos.add(rel)
        if _candidata(rel):
            candidatos.append(rel)
    # Solo se abre el detalle de las primeras candidatas hasta el limite.
    for rel in candidatos[:limite]:
        enlace = urljoin(BASE + "/", rel.lstrip("/"))
        ubicacion = ""
        try:
            detalle = fetch(enlace)
            # Deja el texto plano para buscar la seccion "Ubicacion".
            texto = re.sub(r"<[^>]+>", " ", detalle)
            texto = re.sub(r"\s+", " ", texto)
            m = PATRON_UBICACION.search(texto)
            if m:
                ubicacion = re.sub(r"\s+", " ", m.group(1)).strip()
        except Exception:
            pass
        ofertas.append(
            {
                "titulo": _titulo_desde_slug(rel),
                "empresa": "",
                "ubicacion": ubicacion,
                "url": enlace,
                "fuente": "FindJob24h",
            }
        )
        pausar(pausa)
    return ofertas
