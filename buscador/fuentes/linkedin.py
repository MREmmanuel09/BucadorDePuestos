import html
import re
import urllib.parse

from .comun import fetch, pausar

PLANTILLA = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={kw}&location={loc}&start={start}"
)
TARJETA = re.compile(r"<li>(.*?)</li>", re.S)
TITULO = re.compile(r'class="base-search-card__title">\s*(.*?)\s*</h3>', re.S)
EMPRESA = re.compile(r'class="base-search-card__subtitle">.*?<a[^>]*>\s*(.*?)\s*</a>', re.S)
UBICACION = re.compile(r'class="job-search-card__location">\s*(.*?)\s*</span>', re.S)
ENLACE = re.compile(r'href="(https://[a-z]{2}\.linkedin\.com/jobs/view/[^"?]+)')


def _limpiar(valor):
    texto = re.sub(r"<[^>]+>", " ", valor)
    return html.unescape(re.sub(r"\s+", " ", texto)).strip()


def buscar(cfg):
    ofertas = []
    vistas = set()
    pausa = max(cfg.get("pausa_segundos", 0.7), 1.0)
    paginas = int(cfg.get("max_paginas_por_busqueda", 1))
    ubicaciones = cfg.get("linkedin_ubicaciones", ["Costa Rica"])
    for consulta in cfg.get("palabras_clave_busqueda", []):
        kw = urllib.parse.quote(consulta)
        for loc in ubicaciones:
            for pagina in range(paginas):
                url = PLANTILLA.format(kw=kw, loc=urllib.parse.quote(loc), start=pagina * 25)
                try:
                    html = fetch(url)
                except Exception:
                    break
                tarjetas = TARJETA.findall(html)
                if not tarjetas:
                    break
                for bloque in tarjetas:
                    m_enlace = ENLACE.search(bloque)
                    m_titulo = TITULO.search(bloque)
                    if not m_enlace or not m_titulo:
                        continue
                    enlace = m_enlace.group(1)
                    if enlace in vistas:
                        continue
                    vistas.add(enlace)
                    m_empresa = EMPRESA.search(bloque)
                    m_ubicacion = UBICACION.search(bloque)
                    ofertas.append(
                        {
                            "titulo": _limpiar(m_titulo.group(1)),
                            "empresa": _limpiar(m_empresa.group(1)) if m_empresa else "",
                            "ubicacion": _limpiar(m_ubicacion.group(1)) if m_ubicacion else loc,
                            "url": enlace,
                            "fuente": "LinkedIn",
                        }
                    )
                pausar(pausa)
    return ofertas
