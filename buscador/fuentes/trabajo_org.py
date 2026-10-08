"""Buscador de ofertas en cr.trabajo.org, recorriendo sus paginas por zona."""

import re

from .comun import fetch, pausar

BASE = "https://cr.trabajo.org"
PAGINAS = {
    "alajuela": "Alajuela",
    "grecia": "Grecia",
    "san-jose": "San José",
}
PATRON = re.compile(r'href="(https://cr\.trabajo\.org/oferta-[^"]+)"[^>]*>(.*?)</a>', re.S)
ETIQUETAS = re.compile(r"<[^>]+>")


def _limpiar(valor):
    """Quita etiquetas HTML y espacios de sobra de un fragmento de texto."""
    texto = ETIQUETAS.sub(" ", valor)
    return re.sub(r"\s+", " ", texto).strip(" |")


def buscar(cfg):
    """Recorre las zonas de Trabajo.org y devuelve la lista de ofertas encontradas."""
    ofertas = []
    pausa = cfg.get("pausa_segundos", 0.7)
    for slug, zona in PAGINAS.items():
        url = f"{BASE}/empleo-en-{slug}"
        try:
            html = fetch(url)
        except Exception:
            continue
        for enlace, crudo in PATRON.findall(html):
            titulo = _limpiar(crudo)
            if not titulo or len(titulo) < 4:
                continue
            # Evita duplicados: cada URL solo se agrega una vez.
            if any(o["url"] == enlace for o in ofertas):
                continue
            ofertas.append(
                {
                    "titulo": titulo,
                    "empresa": "",
                    "ubicacion": zona,
                    "url": enlace,
                    "fuente": "Trabajo.org",
                }
            )
        pausar(pausa)
    return ofertas
