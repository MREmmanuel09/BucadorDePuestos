import re
import urllib.parse

from .comun import fetch, pausar

BASE = "https://cr.computrabajo.com"
PATRON = re.compile(r'href="(/ofertas-de-trabajo/oferta-de-trabajo-de-[^"#]+)')
HASH = re.compile(r"-[0-9A-F]{32}$")


def _partir_slug(slug):
    texto = slug.replace("/ofertas-de-trabajo/oferta-de-trabajo-de-", "")
    texto = HASH.sub("", texto)
    if "-en-" in texto:
        titulo, ubicacion = texto.rsplit("-en-", 1)
    else:
        titulo, ubicacion = texto, ""
    return titulo.replace("-", " "), ubicacion.replace("-", " ")


def buscar(cfg):
    ofertas = []
    vistas = set()
    pausa = cfg.get("pausa_segundos", 0.7)
    paginas = int(cfg.get("max_paginas_por_busqueda", 1))
    for consulta in cfg.get("palabras_clave_busqueda", []):
        slug = urllib.parse.quote(consulta.strip().replace(" ", "-"))
        for pagina in range(1, paginas + 1):
            url = f"{BASE}/trabajo-de-{slug}"
            if pagina > 1:
                url += f"?p={pagina}"
            try:
                html = fetch(url)
            except Exception:
                break
            encontrados = PATRON.findall(html)
            if not encontrados:
                break
            for rel in dict.fromkeys(encontrados):
                if rel in vistas:
                    continue
                vistas.add(rel)
                titulo, ubicacion = _partir_slug(rel)
                ofertas.append(
                    {
                        "titulo": titulo.title(),
                        "empresa": "",
                        "ubicacion": ubicacion.title(),
                        "url": BASE + rel,
                        "fuente": "Computrabajo",
                    }
                )
            pausar(pausa)
    return ofertas
