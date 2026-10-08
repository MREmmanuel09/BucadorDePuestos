"""Pruebas de las funciones helper de app.pyw que no necesitan ventana.

Se importa el modulo sin crear ningun widget de Tkinter.
"""

import importlib.util
import os
import sys
import unittest

RUTA_BUSCADOR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "buscador"
)
if RUTA_BUSCADOR not in sys.path:
    sys.path.insert(0, RUTA_BUSCADOR)

RUTA_APP = os.path.join(RUTA_BUSCADOR, "app.pyw")
_spec = importlib.util.spec_from_file_location("app_buscador", RUTA_APP)
app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app)


class PruebaFiltrar(unittest.TestCase):
    """Casos de filtrar(ofertas, texto, estado) sobre datos en memoria."""

    OFERTAS = [
        {"titulo": "Redes y Cableado", "ubicacion": "Alajuela", "empresa": "A",
         "fuente": "Computrabajo", "estado_envio": ""},
        {"titulo": "Soporte Tecnico", "ubicacion": "San Jose", "empresa": "B",
         "fuente": "LinkedIn", "estado_envio": "Postulado"},
        {"titulo": "Help Desk", "ubicacion": "Remoto", "empresa": "C",
         "fuente": "Trabajo.org", "estado_envio": ""},
    ]

    def test_texto_sin_tildes_coincide(self):
        """El filtro de texto ignora tildes y mayusculas."""
        res = app.filtrar(self.OFERTAS, "tecnico")
        self.assertEqual([o["titulo"] for o in res], ["Soporte Tecnico"])

    def test_estado_postulado(self):
        """El filtro por estado muestra solo las marcadas igual."""
        res = app.filtrar(self.OFERTAS, "", "Postulado")
        self.assertEqual([o["titulo"] for o in res], ["Soporte Tecnico"])

    def test_estado_sin_estado(self):
        """'Sin estado' excluye las que ya tienen marcador."""
        res = app.filtrar(self.OFERTAS, "", "Sin estado")
        self.assertEqual([o["titulo"] for o in res], ["Redes y Cableado", "Help Desk"])

    def test_estado_todos(self):
        """'Todos' no descarta nada."""
        self.assertEqual(len(app.filtrar(self.OFERTAS, "", "Todos")), 3)

    def test_texto_y_estado_juntos(self):
        """Texto y estado se aplican a la vez."""
        res = app.filtrar(self.OFERTAS, "soporte", "Postulado")
        self.assertEqual([o["titulo"] for o in res], ["Soporte Tecnico"])


class PruebaPythonConsola(unittest.TestCase):
    """Pruebas de python_consola (ruta del interprete para subprocess)."""

    def test_devuelve_interprete_de_consola(self):
        """python_consola devuelve python.exe aunque se corra con pythonw."""
        original = sys.executable
        try:
            falso = os.path.join(os.path.dirname(original), "pythonw.exe")
            sys.executable = falso
            ruta = app.python_consola()
            self.assertTrue(ruta.endswith("python.exe"), ruta)
            self.assertTrue(os.path.exists(ruta), ruta)
        finally:
            sys.executable = original
        self.assertTrue(app.python_consola().endswith("python.exe"))


class PruebaEstadisticas(unittest.TestCase):
    """Pruebas de calcular_estadisticas (resumen para la ventana de estadisticas)."""

    OFERTAS = [
        {"fecha": "2999-01-01", "fuente": "LinkedIn", "estado_envio": "Postulado"},
        {"fecha": "2999-01-01", "fuente": "LinkedIn", "estado_envio": ""},
        {"fecha": "2999-01-02", "fuente": "Computrabajo", "estado_envio": "Descartado"},
        {"fecha": "2000-01-01", "fuente": "Computrabajo", "estado_envio": ""},
        {"fecha": "", "fuente": "", "estado_envio": ""},
    ]

    def test_totales_y_estados(self):
        """Cuenta el total y reparte por estado (vacio cuenta como sin estado)."""
        datos = app.calcular_estadisticas(self.OFERTAS, hoy="2999-01-03")
        self.assertEqual(datos["total"], 5)
        self.assertEqual(datos["estados"],
                         {"postuladas": 1, "descartadas": 1, "sin_estado": 3})

    def test_por_dia_siete_dias(self):
        """Devuelve exactamente 7 dias ascendentes con los conteos de cada uno."""
        datos = app.calcular_estadisticas(self.OFERTAS, hoy="2999-01-07")
        self.assertEqual(len(datos["por_dia"]), 7)
        self.assertEqual(datos["por_dia"][0][0], "2999-01-01")
        self.assertEqual(datos["por_dia"][-1], ("2999-01-07", 0))
        self.assertEqual(dict(datos["por_dia"])["2999-01-01"], 2)
        self.assertEqual(dict(datos["por_dia"])["2999-01-02"], 1)

    def test_fuentes_ordenadas_por_conteo(self):
        """Las fuentes salen de mayor a menor; la vacia queda como 'Otra'."""
        datos = app.calcular_estadisticas(self.OFERTAS, hoy="2999-01-03")
        self.assertEqual(datos["fuentes"][0], ("Computrabajo", 2))
        self.assertEqual(datos["fuentes"][1], ("LinkedIn", 2))
        self.assertIn(("Otra", 1), datos["fuentes"])


class PruebaConfigParcial(unittest.TestCase):
    """Pruebas de guardar_config_parcial (fusion claves en config.json)."""

    def setUp(self):
        """Redirige el config (main y app) a un temporal."""
        import tempfile
        import main
        self.tmp = tempfile.mkdtemp(prefix="cfg_test_")
        self._orig = (main.CONFIG_PATH, main.EJEMPLO_CONFIG_PATH, app.CONFIG_PATH)
        main.CONFIG_PATH = os.path.join(self.tmp, "config.json")
        main.EJEMPLO_CONFIG_PATH = os.path.join(self.tmp, "sin_ejemplo.json")
        app.CONFIG_PATH = main.CONFIG_PATH

    def tearDown(self):
        """Restaura el config original y borra el temporal."""
        import shutil
        import main
        main.CONFIG_PATH, main.EJEMPLO_CONFIG_PATH, app.CONFIG_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fusiona_sin_tocar_otros(self):
        """guardar_config_parcial agrega la clave y conserva las demas."""
        import json
        import main
        app.guardar_config_parcial({"app_auto_minutos": 10})
        with open(main.CONFIG_PATH, encoding="utf-8") as f:
            datos = json.load(f)
        self.assertEqual(datos["app_auto_minutos"], 10)
        self.assertIn("palabras_clave", datos)


if __name__ == "__main__":
    unittest.main()
