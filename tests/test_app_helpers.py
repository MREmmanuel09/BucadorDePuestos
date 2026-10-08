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


if __name__ == "__main__":
    unittest.main()
