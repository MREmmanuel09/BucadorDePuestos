"""Utilidades comunes: descarga de paginas, pausas y limpieza de texto."""

import ssl
import time
import unicodedata
import urllib.request

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Encoding": "identity",
    "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
}

CTX = ssl.create_default_context()


def fetch(url, timeout=30):
    """Descarga una pagina web y devuelve su HTML como texto."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def pausar(segundos):
    """Espera los segundos indicados; no hace nada si son 0 o negativos."""
    if segundos and segundos > 0:
        time.sleep(segundos)


def sin_acentos(texto):
    """Convierte el texto a minusculas y elimina tildes/diacriticos."""
    forma = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in forma if not unicodedata.combining(c))
