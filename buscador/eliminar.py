"""Borrado manual de ofertas desde la terminal.

Ofrece un menú interactivo o purga directa por antigüedad con --dias;
las ofertas borradas se mueven a la lista negra del buscador.
"""

import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from main import (
    OFERTAS_PATH,
    cargar_config,
    cargar_ofertas,
    eliminar_ofertas,
    purgar_ofertas,
    refrescar_reporte,
    registrar,
)

RETENCION_DEFECTO = 15


def listar(ofertas):
    """Muestra una tabla numerada de las ofertas recibidas.

    Recibe la lista a imprimir; no devuelve nada. El * marca ofertas con
    estado_envio, que no se purgan por antigüedad.
    """
    print(f"{'#':>3}  {'Fecha':10}  {'Fuente':13} {'Titulo':52} Ubicacion")
    for i, o in enumerate(ofertas, 1):
        marcada = (o.get("estado_envio") or "").strip()
        marca = " *" if marcada else ""
        print(
            f"{i:>3}  {o.get('fecha', ''):10}  {o.get('fuente', ''):13} "
            f"{o.get('titulo', '')[:52]:52} {o.get('ubicacion', '')[:34]}{marca}"
        )
    print(f"\n  Total: {len(ofertas)}  (* = marcada con estado_envio, no se purga)")


def purgar(dias):
    """Elimina del CSV las ofertas con más de N días y las manda a lista negra.

    Recibe el número de días de antigüedad; devuelve cuántas se borraron.
    """
    if not os.path.exists(OFERTAS_PATH):
        print("ofertas.csv no existe aun.")
        return 0
    antes, borradas = purgar_ofertas(dias)
    refrescar_reporte(borradas)
    print(f"Purga >{dias} dias: {borradas} borradas (a lista negra {dias_lista()} dias), {antes - borradas} restantes.")
    return borradas


def dias_lista():
    """Lee de la configuración los días que dura la lista negra.

    No recibe nada; devuelve el valor o 15 si falta o no es válido.
    """
    try:
        return int(cargar_config().get("dias_lista_negra", 15))
    except Exception:
        return 15


def borrar_seleccionadas(ofertas):
    """Pide por teclado los números del listado y borra esas ofertas.

    Recibe la lista de ofertas; muestra confirmación previa y no devuelve
    nada (se cancela con Enter o entradas fuera de rango).
    """
    listar(ofertas)
    texto = input("\nNumeros a borrar (ej: 1,5,9) o Enter para cancelar: ").strip()
    if not texto:
        print("Cancelado.")
        return
    try:
        # de mayor a menor para que al borrar no se desplacen los números
        indices = sorted({int(p.strip()) for p in texto.split(",") if p.strip()}, reverse=True)
    except ValueError:
        print("Entrada invalida.")
        return
    if any(i < 1 or i > len(ofertas) for i in indices):
        print("Numeros fuera de rango.")
        return
    a_borrar = [ofertas[i - 1] for i in indices]
    for o in a_borrar:
        print(f"  - {o.get('titulo', '')} ({o.get('fecha', '')})")
    if input(f"¿Borrar {len(a_borrar)} oferta(s)? (s/N): ").strip().lower() != "s":
        print("Cancelado.")
        return
    borradas = eliminar_ofertas([o.get("url", "") for o in a_borrar])
    refrescar_reporte(borradas)
    restantes = len(cargar_ofertas())
    print(f"Listo: {borradas} borradas y en lista negra {dias_lista()} dias, {restantes} restantes.")


def menu():
    """Menú interactivo para purgar por antigüedad o borrar ofertas puntuales.

    No recibe nada; se repite hasta que el usuario elige salir.
    """
    retencion = RETENCION_DEFECTO
    try:
        retencion = int(cargar_config().get("dias_retencion", RETENCION_DEFECTO))
    except Exception:
        pass
    while True:
        print("\n=== Borrar ofertas (ofertas.csv) ===")
        print(f"1) Purgar por antiguedad (> {retencion} dias, configurado)")
        print("2) Purgar por antiguedad (> 7 dias)")
        print("3) Borrar seleccionadas (por numero, a lista negra)")
        print("4) Ver lista completa")
        print("5) Salir")
        opcion = input("Opcion: ").strip()
        if opcion == "1":
            purgar(retencion)
        elif opcion == "2":
            purgar(7)
        elif opcion == "3":
            if os.path.exists(OFERTAS_PATH):
                borrar_seleccionadas(cargar_ofertas())
            else:
                print("ofertas.csv no existe aun.")
        elif opcion == "4":
            if os.path.exists(OFERTAS_PATH):
                listar(cargar_ofertas())
            else:
                print("ofertas.csv no existe aun.")
        elif opcion == "5":
            return
        else:
            print("Opcion no valida.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Borrar ofertas de ofertas.csv")
    parser.add_argument("--dias", type=int, help="Purgar ofertas con mas de N dias y salir")
    args = parser.parse_args()
    try:
        if args.dias is not None:
            purgar(args.dias)
        else:
            menu()
    except Exception:
        import traceback

        registrar("ERROR eliminar " + traceback.format_exc().replace("\n", " | "))
        raise
