"""Utilidades comunes: descarga de paginas, pausas y limpieza de texto."""

import ssl
import time
import unicodedata
import urllib.error
import urllib.request

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Encoding": "identity",
    "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
}

CTX = ssl.create_default_context()


def descargar(url, timeout=30, intentos=3):
    """Descarga una pagina y devuelve (codigo HTTP, url final, HTML).

    Reintenta hasta 'intentos' veces con espera creciente (1.5s, 3s...) ante
    timeouts, errores de red y respuestas 5xx; los 4xx se propagan de inmediato
    para no reintentar algo que no existe (p. ej. un 404).
    """
    ultimo_error = None
    for intento in range(1, intentos + 1):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise
            ultimo_error = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            ultimo_error = e
        if intento < intentos:
            time.sleep(1.5 * intento)
    raise ultimo_error


def fetch(url, timeout=30):
    """Descarga una pagina web y devuelve su HTML como texto (con reintentos)."""
    return descargar(url, timeout)[2]


def pausar(segundos):
    """Espera los segundos indicados; no hace nada si son 0 o negativos."""
    if segundos and segundos > 0:
        time.sleep(segundos)


def sin_acentos(texto):
    """Convierte el texto a minusculas y elimina tildes/diacriticos."""
    forma = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in forma if not unicodedata.combining(c))
