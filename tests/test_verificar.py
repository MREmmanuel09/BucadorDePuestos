"""Pruebas del verificador de ofertas cerradas (verificar.py).

Usa una funcion de descarga falsa: no se hace ninguna peticion de red y
los CSV se escriben en un tempdir, nunca en data/ real.
"""

import os
import shutil
import sys
import tempfile
import unittest
import urllib.error

RUTA_BUSCADOR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "buscador"
)
if RUTA_BUSCADOR not in sys.path:
    sys.path.insert(0, RUTA_BUSCADOR)

import main  # noqa: E402
import verificar  # noqa: E402


def _html(contenido="", relleno=2200):
    """Devuelve un HTML de mas de 2000 caracteres (minimo del clasificador)."""
    return f"<html><body>{contenido} {'x' * relleno}</body></html>"


def _ok(html, final=None):
    """Respuesta falsa exitosa: (codigo, url final, html)."""
    return 200, final or "https://ejemplo.com/oferta", html


class BasePrueba(unittest.TestCase):
    """Base: rutas de main redirigidas a un tempdir durante cada prueba."""

    def setUp(self):
        """Apunta las rutas de main a un directorio temporal."""
        self.tmp = tempfile.mkdtemp(prefix="verificar_test_")
        claves = ("DATA", "CONFIG_PATH", "EJEMPLO_CONFIG_PATH", "VISTAS_PATH",
                  "OFERTAS_PATH", "REPORTE_PATH", "LOG_PATH", "NEGRA_PATH")
        self._originales = {c: getattr(main, c) for c in claves}
        main.DATA = self.tmp
        main.CONFIG_PATH = os.path.join(self.tmp, "config.json")
        main.EJEMPLO_CONFIG_PATH = os.path.join(self.tmp, "sin_ejemplo.json")
        main.VISTAS_PATH = os.path.join(self.tmp, "vistas.json")
        main.OFERTAS_PATH = os.path.join(self.tmp, "ofertas.csv")
        main.REPORTE_PATH = os.path.join(self.tmp, "reporte.html")
        main.LOG_PATH = os.path.join(self.tmp, "historial.log")
        main.NEGRA_PATH = os.path.join(self.tmp, "lista_negra.json")

    def tearDown(self):
        """Restaura las rutas originales y borra el temporal."""
        for clave, valor in self._originales.items():
            setattr(main, clave, valor)
        shutil.rmtree(self.tmp, ignore_errors=True)


class PruebaValidthrough(unittest.TestCase):
    """Pruebas de la extraccion de la fecha de expiracion."""

    def test_iso_con_hora(self):
        """Formato ISO con hora (LinkedIn): conserva solo la fecha."""
        html = '"validthrough": "2026-11-05T23:59:59+01:00"'
        self.assertEqual(verificar._validthrough(html), "2026-11-05")

    def test_con_espacio(self):
        """Formato con espacio (Trabajo.org/FindJob24h)."""
        html = 'validthrough": "2026-10-22 05:22:19"'
        self.assertEqual(verificar._validthrough(html), "2026-10-22")

    def test_sin_comillas(self):
        """Formato sin comillas alrededor de la fecha."""
        html = "validthrough: 2026-10-30"
        self.assertEqual(verificar._validthrough(html), "2026-10-30")

    def test_ausente(self):
        """Sin el metadato devuelve None."""
        self.assertIsNone(verificar._validthrough('{"jobDate": "2026-01-01"}'))


class PruebaIdComputrabajo(unittest.TestCase):
    """Pruebas de la extraccion del ID de Computrabajo."""

    def test_extrae_id_final(self):
        """La URL con sufijo hexadecimal devuelve el ID."""
        url = ("https://cr.computrabajo.com/oferta-de-trabajo-de-soporte"
               "-en-alajuela-9863541558f3693f61373e686dcf3405")
        self.assertEqual(
            verificar._id_computrabajo(url), "9863541558f3693f61373e686dcf3405"
        )

    def test_otra_fuente_devuelve_none(self):
        """URLs de otras fuentes (sin ID hex largo) devuelven None."""
        self.assertIsNone(verificar._id_computrabajo("https://cr.linkedin.com/jobs/view/x-123"))


class PruebaEstadoOferta(unittest.TestCase):
    """Pruebas del clasificador viva/cerrada/desconocida."""

    def test_viva_sin_marcas(self):
        """Pagina larga sin evidencia de cierre se clasifica viva."""
        oferta = {"url": "https://x.com/o", "fuente": "LinkedIn"}
        self.assertEqual(verificar.estado_oferta(oferta, lambda u: _ok(_html())), "viva")

    def test_cerrada_por_texto(self):
        """El texto de cierre es evidencia suficiente."""
        oferta = {"url": "https://x.com/o", "fuente": "LinkedIn"}
        html = _html("para este puesto ya no se aceptan solicitudes")
        self.assertEqual(verificar.estado_oferta(oferta, lambda u: _ok(html)), "cerrada")

    def test_cerrada_por_validthrough_vencido(self):
        """Una fecha de expiracion pasada marca la oferta como cerrada."""
        oferta = {"url": "https://x.com/o", "fuente": "Trabajo.org"}
        html = _html('"validthrough": "2000-01-01T00:00:00+00:00"')
        self.assertEqual(verificar.estado_oferta(oferta, lambda u: _ok(html)), "cerrada")

    def test_viva_con_validthrough_futuro(self):
        """Una fecha de expiracion futura no retira la oferta."""
        oferta = {"url": "https://x.com/o", "fuente": "Trabajo.org"}
        html = _html('"validthrough": "2999-01-01"')
        self.assertEqual(verificar.estado_oferta(oferta, lambda u: _ok(html)), "viva")

    def test_404_es_cerrada(self):
        """Un 404/410 es evidencia positiva de que la oferta ya no existe."""
        oferta = {"url": "https://x.com/o", "fuente": "LinkedIn"}

        def fallo(u):
            raise urllib.error.HTTPError(u, 404, "Not Found", {}, None)

        self.assertEqual(verificar.estado_oferta(oferta, fallo), "cerrada")

    def test_error_de_red_no_borra(self):
        """Un timeout o fallo de red devuelve desconocida: jamas borra."""
        oferta = {"url": "https://x.com/o", "fuente": "LinkedIn"}

        def fallo(u):
            raise urllib.error.URLError("timeout")

        self.assertEqual(verificar.estado_oferta(oferta, fallo), "desconocida")

    def test_pagina_corta_es_desconocida(self):
        """HTML demasiado corto (redirecciones raros) no se toma como cierre."""
        oferta = {"url": "https://x.com/o", "fuente": "LinkedIn"}
        self.assertEqual(
            verificar.estado_oferta(oferta, lambda u: _ok("<html>ok</html>")),
            "desconocida",
        )

    def test_computrabajo_id_perdido_es_cerrada(self):
        """Si el ID desaparece de la URL final, Computrabajo cerro la oferta."""
        url = ("https://cr.computrabajo.com/oferta-de-soporte-"
               "9863541558f3693f61373e686dcf3405")
        oferta = {"url": url, "fuente": "Computrabajo"}
        html = _html()
        self.assertEqual(
            verificar.estado_oferta(oferta, lambda u: (200, "https://cr.computrabajo.com/", html)),
            "cerrada",
        )


class PruebaVerificarOfertas(BasePrueba):
    """Pruebas de corrida completa con descarga falsa."""

    def test_retira_cerrada_y_conserva_viva(self):
        """Retira la cerrada del CSV y la enlista; la viva se queda."""
        main.guardar_ofertas([
            {"fecha": "2000-01-01", "fuente": "LinkedIn", "titulo": "Cerrada",
             "ubicacion": "Alajuela", "empresa": "E", "url": "https://x.com/c",
             "estado_envio": ""},
            {"fecha": "2000-01-01", "fuente": "LinkedIn", "titulo": "Viva",
             "ubicacion": "Alajuela", "empresa": "E", "url": "https://x.com/v",
             "estado_envio": ""},
        ])
        paginas = {
            "https://x.com/c": _ok(_html("oferta finalizada")),
            "https://x.com/v": _ok(_html()),
        }
        retiradas, revisadas = verificar.verificar_ofertas(
            main.cargar_config(), obtener_fn=lambda u: paginas[u]
        )
        self.assertEqual((len(retiradas), revisadas), (1, 2))
        restantes = main.cargar_ofertas()
        self.assertEqual([o["titulo"] for o in restantes], ["Viva"])
        self.assertIn("https://x.com/c", main.cargar_lista_negra())


if __name__ == "__main__":
    unittest.main()
