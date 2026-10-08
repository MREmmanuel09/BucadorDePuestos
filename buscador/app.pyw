import json
import os
import queue
import subprocess
import sys
import threading

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import tkinter as tk
from tkinter import messagebox, ttk

from fuentes.comun import sin_acentos
from main import (
    CONFIG_PATH,
    cargar_config,
    cargar_lista_negra,
    cargar_ofertas,
    clave_url,
    eliminar_ofertas,
    guardar_lista_negra,
    guardar_ofertas,
    purgar_lista_negra,
    refrescar_reporte,
    registrar,
)

COLORES = {
    "fondo": "#F4F6F9",
    "encabezado": "#1A5276",
    "acento": "#2E86C1",
    "acento_oscuro": "#1F6F8B",
    "peligro": "#C0392B",
    "verde": "#1E8449",
    "texto": "#2C3E50",
    "fila": "#EAF2F8",
    "blanco": "#FFFFFF",
}


def filtrar(ofertas, texto="", estado="Todos"):
    t = sin_acentos(texto.strip()) if texto else ""
    salida = []
    for o in ofertas:
        if t:
            hay = sin_acentos(
                f"{o.get('titulo', '')} {o.get('ubicacion', '')} {o.get('empresa', '')} {o.get('fuente', '')}"
            )
            if t not in hay:
                continue
        est = (o.get("estado_envio") or "").strip()
        if estado == "Sin estado" and est:
            continue
        if estado in ("Postulado", "Descartado") and est != estado:
            continue
        salida.append(o)
    return salida


def aplicar_estado(urls, estado):
    claves = {clave_url(u) for u in urls}
    ofertas = cargar_ofertas()
    n = 0
    for o in ofertas:
        if clave_url(o.get("url", "")) in claves:
            o["estado_envio"] = estado
            n += 1
    if n:
        guardar_ofertas(ofertas)
        refrescar_reporte(0)
        registrar(f"ESTADO '{estado}' filas={n}")
    return n


def restaurar_negra(urls):
    claves = {clave_url(u) for u in urls}
    negra = cargar_lista_negra()
    n = 0
    for k in claves:
        if k in negra:
            negra.pop(k)
            n += 1
    if n:
        guardar_lista_negra(negra)
        registrar(f"NEGRA restauradas={n}")
    return n


def python_consola():
    exe = sys.executable or ""
    if exe.lower().endswith("pythonw.exe"):
        candidato = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(candidato):
            return candidato
    return exe or "python"


def dias_de(fecha, hoy):
    from datetime import datetime

    try:
        return (datetime.strptime(hoy, "%Y-%m-%d") - datetime.strptime(fecha, "%Y-%m-%d")).days
    except Exception:
        return None


class Aplicacion:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cola = queue.Queue()
        self.trabajando = False
        self.ofertas = []
        self.negra = {}
        self._estilos()
        self._construir()
        self.recargar()

    def _estilos(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", font=("Segoe UI", 10), background=COLORES["fondo"], foreground=COLORES["texto"])
        s.configure("TFrame", background=COLORES["fondo"])
        s.configure("Fondo.TFrame", background=COLORES["encabezado"])
        s.configure("Toolbar.TFrame", background=COLORES["fondo"])
        s.configure(
            "TButton",
            background=COLORES["acento"],
            foreground=COLORES["blanco"],
            borderwidth=0,
            padding=(12, 7),
            font=("Segoe UI", 10, "bold"),
        )
        s.map("TButton", background=[("active", COLORES["acento_oscuro"]), ("disabled", "#AAB7C4")],
              foreground=[("disabled", "#EEF2F5")])
        s.configure("Peligro.TButton", background=COLORES["peligro"])
        s.map("Peligro.TButton", background=[("active", "#96281B"), ("disabled", "#AAB7C4")])
        s.configure("Verde.TButton", background=COLORES["verde"])
        s.map("Verde.TButton", background=[("active", "#196F3D"), ("disabled", "#AAB7C4")])
        s.configure("Treeview", background=COLORES["blanco"], fieldbackground=COLORES["blanco"],
                    foreground=COLORES["texto"], rowheight=27, font=("Segoe UI", 10))
        s.map("Treeview", background=[("selected", COLORES["acento"])],
              foreground=[("selected", COLORES["blanco"])])
        s.configure("Treeview.Heading", background=COLORES["encabezado"], foreground=COLORES["blanco"],
                    font=("Segoe UI", 10, "bold"), padding=(8, 7))
        s.map("Treeview.Heading", background=[("active", COLORES["encabezado"])])
        s.configure("TEntry", fieldbackground=COLORES["blanco"], padding=(8, 6))
        s.configure("TCombobox", padding=(8, 6))
        s.configure("Horizontal.TProgressbar", background=COLORES["acento"], troughcolor="#DCE4EC")

    def _construir(self):
        r = self.raiz
        r.title("Mis Ofertas TI - Buscador de Puestos")
        r.geometry("1080x640")
        r.minsize(860, 480)
        r.configure(bg=COLORES["fondo"])

        cab = tk.Frame(r, bg=COLORES["encabezado"], padx=16, pady=12)
        cab.pack(fill="x")
        tk.Label(cab, text="\U0001F4CB Mis Ofertas TI", bg=COLORES["encabezado"],
                 fg=COLORES["blanco"], font=("Segoe UI", 15, "bold")).pack(side="left")
        self.badges = tk.Label(cab, text="", bg=COLORES["encabezado"], fg="#D6EAF8",
                               font=("Segoe UI", 10))
        self.badges.pack(side="right")

        barra = tk.Frame(r, bg=COLORES["fondo"], padx=12, pady=10)
        barra.pack(fill="x")
        self.btn_buscar = ttk.Button(barra, text="\U0001F504 Buscar ahora", command=self.accion_buscar)
        self.btn_verificar = ttk.Button(barra, text="\U0001F50E Verificar disponibilidad",
                                        command=self.accion_verificar)
        self.btn_eliminar = ttk.Button(barra, text="\U0001F5D1 Eliminar seleccionadas",
                                       style="Peligro.TButton", command=self.accion_eliminar)
        self.btn_negra = ttk.Button(barra, text="\U0001F4DC Lista negra",
                                    command=self.accion_negra)
        for b in (self.btn_buscar, self.btn_verificar, self.btn_eliminar, self.btn_negra):
            b.pack(side="left", padx=(0, 8))

        tk.Label(barra, text="Marcar:", bg=COLORES["fondo"]).pack(side="left", padx=(6, 4))
        self.combo_estado_accion = ttk.Combobox(barra, values=["Postulado", "Descartado", "(vacio)"],
                                                state="readonly", width=12)
        self.combo_estado_accion.set("Postulado")
        self.combo_estado_accion.pack(side="left", padx=(0, 4))
        self.btn_marcar = ttk.Button(barra, text="Aplicar", style="Verde.TButton",
                                     command=self.accion_marcar)
        self.btn_marcar.pack(side="left", padx=(0, 8))
        self._set_habilitado(False, self.btn_eliminar, self.btn_marcar)

        self.btn_perfil = ttk.Button(barra, text="\U0001F4DD Editar perfil",
                                     command=self.accion_perfil)
        self.btn_perfil.pack(side="left", padx=(4, 0))

        self.progreso = ttk.Progressbar(barra, mode="indeterminate", length=140)

        filtro = tk.Frame(r, bg=COLORES["fondo"], padx=12)
        filtro.pack(fill="x", pady=(0, 8))
        tk.Label(filtro, text="\U0001F50D Filtrar:", bg=COLORES["fondo"]).pack(side="left")
        self.var_texto = tk.StringVar()
        self.var_texto.trace_add("write", lambda *a: self.pintar())
        entrada = ttk.Entry(filtro, textvariable=self.var_texto, width=36)
        entrada.pack(side="left", padx=(6, 14))
        tk.Label(filtro, text="Estado:", bg=COLORES["fondo"]).pack(side="left")
        self.var_filtro_estado = tk.StringVar(value="Todos")
        combo = ttk.Combobox(filtro, textvariable=self.var_filtro_estado, state="readonly",
                             values=["Todos", "Sin estado", "Postulado", "Descartado"], width=14)
        combo.pack(side="left", padx=(6, 0))
        combo.bind("<<ComboboxSelected>>", lambda e: self.pintar())
        tk.Label(filtro, text="Orden:", bg=COLORES["fondo"]).pack(side="left", padx=(18, 4))
        self.var_orden = tk.StringVar(value="Mas nuevos primero")
        combo_orden = ttk.Combobox(filtro, textvariable=self.var_orden, state="readonly",
                                   values=["Mas nuevos primero", "Mas viejos primero"], width=19)
        combo_orden.pack(side="left")
        combo_orden.bind("<<ComboboxSelected>>", lambda e: self.pintar())
        tk.Label(filtro, text="Seleccionar:", bg=COLORES["fondo"]).pack(side="left", padx=(18, 4))
        ttk.Button(filtro, text="Todo", width=6, command=self.seleccionar_todo).pack(side="left", padx=(0, 4))
        ttk.Button(filtro, text="Ninguno", width=8, command=self.limpiar_seleccion).pack(side="left")

        marco_tabla = tk.Frame(r, padx=12, pady=0)
        marco_tabla.pack(fill="both", expand=True)
        cols = ("titulo", "fuente", "ubicacion", "dias", "estado")
        self.tabla = ttk.Treeview(marco_tabla, columns=cols, show="headings", selectmode="extended")
        self.tabla.heading("titulo", text="Puesto")
        self.tabla.heading("fuente", text="Fuente")
        self.tabla.heading("ubicacion", text="Ubicacion")
        self.tabla.heading("dias", text="Dias")
        self.tabla.heading("estado", text="Estado")
        self.tabla.column("titulo", width=430, anchor="w")
        self.tabla.column("fuente", width=110, anchor="center")
        self.tabla.column("ubicacion", width=250, anchor="w")
        self.tabla.column("dias", width=55, anchor="center")
        self.tabla.column("estado", width=110, anchor="center")
        scroll = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tabla.tag_configure("nueva", font=("Segoe UI", 10, "bold"))
        self.tabla.tag_configure("marcada", foreground=COLORES["verde"])
        self.tabla.tag_configure("alt", background=COLORES["fila"])
        self.tabla.bind("<Double-1>", self.abrir_oferta)
        self.tabla.bind("<<TreeviewSelect>>", self.al_seleccionar)
        self.tabla.bind("<Control-a>", self.seleccionar_todo)
        self.tabla.bind("<Control-A>", self.seleccionar_todo)

        pie = tk.Frame(r, bg="#DCE4EC", padx=12, pady=7)
        pie.pack(fill="x", side="bottom")
        self.lbl_mensaje = tk.Label(pie, text="Listo.  Ctrl/Shift+clic = elegir varios  \u2022  Ctrl+A = todo",
                                    bg="#DCE4EC", fg=COLORES["texto"],
                                    font=("Segoe UI", 10))
        self.lbl_mensaje.pack(side="left")
        self.lbl_cuentas = tk.Label(pie, text="", bg="#DCE4EC", fg="#5D6D7E",
                                    font=("Segoe UI", 10))
        self.lbl_cuentas.pack(side="right")

    def _set_habilitado(self, activo, *botones):
        for b in botones:
            if activo:
                b.state(["!disabled"])
            else:
                b.state(["disabled"])

    def mensaje(self, texto, color=None):
        self.lbl_mensaje.config(text=texto, fg=color or COLORES["texto"])
        self.raiz.update_idletasks()

    def recargar(self):
        self.ofertas = cargar_ofertas()
        self.negra = purgar_lista_negra()
        hoy = datetime_hoy()
        nuevas = sum(1 for o in self.ofertas if (o.get("fecha") or "") == hoy)
        self.badges.config(
            text=f"{len(self.ofertas)} activas   \u2022   {len(self.negra)} en lista negra"
            f"   \u2022   {nuevas} nuevas hoy"
        )
        self.lbl_cuentas.config(text=f"{len(self.ofertas)} ofertas")
        self.pintar()

    def pintar(self):
        self.tabla.delete(*self.tabla.get_children())
        hoy = datetime_hoy()
        visibles = filtrar(self.ofertas, self.var_texto.get(), self.var_filtro_estado.get())
        visibles = sorted(
            visibles,
            key=lambda o: o.get("fecha") or "",
            reverse=(self.var_orden.get() != "Mas viejos primero"),
        )
        for i, o in enumerate(visibles):
            est = (o.get("estado_envio") or "").strip()
            dias = dias_de(o.get("fecha", ""), hoy)
            etiquetas = []
            if (o.get("fecha") or "") == hoy:
                etiquetas.append("nueva")
            if est:
                etiquetas.append("marcada")
            if i % 2 == 1:
                etiquetas.append("alt")
            self.tabla.insert(
                "", "end",
                iid=o.get("url", f"fila{i}"),
                values=(o.get("titulo", ""), o.get("fuente", ""), o.get("ubicacion", ""),
                        dias if dias is not None else "-", est),
                tags=tuple(etiquetas),
            )
        if not visibles:
            self.mensaje("Sin ofertas que mostrar. Pulsa 'Buscar ahora' o ajusta el filtro.")
        self.lbl_cuentas.config(text=f"{len(self.ofertas)} ofertas")

    def urls_seleccionadas(self):
        return list(self.tabla.selection())

    def al_seleccionar(self, _=None):
        n = len(self.urls_seleccionadas())
        self._set_habilitado(n > 0, self.btn_eliminar, self.btn_marcar)
        base = f"{len(self.ofertas)} ofertas"
        self.lbl_cuentas.config(text=f"{base}   \u2022   {n} seleccionadas" if n else base)

    def seleccionar_todo(self, _=None):
        hijos = self.tabla.get_children()
        if hijos:
            self.tabla.selection_set(hijos)
            self.tabla.focus(hijos[-1])
            self.tabla.see(hijos[0])
        self.al_seleccionar()

    def limpiar_seleccion(self, _=None):
        self.tabla.selection_remove(self.tabla.selection())
        self.al_seleccionar()

    def abrir_oferta(self, _=None):
        sel = self.urls_seleccionadas()
        if sel:
            try:
                os.startfile(sel[0])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir la oferta: {e}")

    def _ocupado(self, activo):
        self.trabajando = activo
        estado = ["disabled"] if activo else ["!disabled"]
        for b in (self.btn_buscar, self.btn_verificar, self.btn_negra, self.btn_perfil):
            b.state(estado)
        self.al_seleccionar()
        if activo:
            self.progreso.pack(side="right")
            self.progreso.start(12)
        else:
            self.progreso.stop()
            self.progreso.pack_forget()

    def accion_eliminar(self):
        sel = self.urls_seleccionadas()
        if not sel:
            return
        if not messagebox.askyesno(
            "Eliminar ofertas",
            f"¿Eliminar {len(sel)} oferta(s) seleccionada(s)?\n\n"
            "No volveran a aparecer por 15 dias (lista negra).",
        ):
            return
        try:
            n = eliminar_ofertas(sel)
            refrescar_reporte(0)
            self.recargar()
            self.mensaje(f"{n} oferta(s) eliminada(s). Lista negra: 15 dias.", COLORES["verde"])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar: {e}")
            self.mensaje("Error al eliminar.", COLORES["peligro"])

    def accion_marcar(self):
        sel = self.urls_seleccionadas()
        if not sel:
            return
        valor = self.combo_estado_accion.get()
        estado = "" if valor == "(vacio)" else valor
        try:
            n = aplicar_estado(sel, estado)
            self.recargar()
            self.mensaje(f"{n} oferta(s) marcada(s) como '{valor}'.", COLORES["verde"])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo marcar: {e}")

    def accion_negra(self):
        top = tk.Toplevel(self.raiz)
        top.title("Lista negra (15 dias)")
        top.geometry("760x420")
        top.configure(bg=COLORES["fondo"])
        tk.Label(
            top,
            text="Ofertas eliminadas: el sistema no las trae de nuevo hasta la fecha indicada.",
            bg=COLORES["fondo"], fg=COLORES["texto"], font=("Segoe UI", 10), pady=8,
        ).pack(fill="x", padx=12)
        marco = tk.Frame(top, padx=12)
        marco.pack(fill="both", expand=True)
        t = ttk.Treeview(marco, columns=("titulo", "fuente", "hasta", "restan"), show="headings",
                         selectmode="extended")
        t.heading("titulo", text="Puesto")
        t.heading("fuente", text="Fuente")
        t.heading("hasta", text="Hasta")
        t.heading("restan", text="Dias restantes")
        t.column("titulo", width=380, anchor="w")
        t.column("fuente", width=110, anchor="center")
        t.column("hasta", width=110, anchor="center")
        t.column("restan", width=100, anchor="center")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=scroll.set)
        t.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        hoy = datetime_hoy()

        def pintar_negra():
            t.delete(*t.get_children())
            negra = cargar_lista_negra()
            for url, info in negra.items():
                hasta = info.get("hasta", "")
                try:
                    from datetime import datetime

                    restan = (datetime.strptime(hasta, "%Y-%m-%d") - datetime.strptime(hoy, "%Y-%m-%d")).days
                except Exception:
                    restan = "-"
                t.insert("", "end", iid=url,
                         values=(info.get("titulo") or "(sin titulo, ver URL al restaurar)",
                                 info.get("fuente", ""), hasta, restan))

        pintar_negra()

        def restaurar():
            sel = list(t.selection())
            if not sel:
                return
            if not messagebox.askyesno("Restaurar", f"¿Devolver {len(sel)} oferta(s) a la busqueda?", parent=top):
                return
            n = restaurar_negra(sel)
            pintar_negra()
            self.recargar()
            self.mensaje(f"{n} oferta(s) fuera de la lista negra.", COLORES["verde"])

        barra = tk.Frame(top, bg=COLORES["fondo"], pady=10, padx=12)
        barra.pack(fill="x")
        ttk.Button(barra, text="Restaurar seleccionadas", style="Verde.TButton",
                   command=restaurar).pack(side="left")
        ttk.Button(barra, text="Cerrar", command=top.destroy).pack(side="right")

    def accion_perfil(self):
        cfg = cargar_config()
        top = tk.Toplevel(self.raiz)
        top.title("Editar perfil de busqueda")
        top.geometry("560x660")
        top.configure(bg=COLORES["fondo"])
        tk.Label(
            top,
            text="Define tus zonas y palabras. Se usan en cada busqueda nueva.",
            bg=COLORES["fondo"], fg=COLORES["texto"], font=("Segoe UI", 10), pady=8,
        ).pack(fill="x", padx=12)
        marco = tk.Frame(top, bg=COLORES["fondo"], padx=14, pady=4)
        marco.pack(fill="both", expand=True)
        campos = (
            ("Zonas (una por linea)", "zonas", 4),
            ("Terminos de busqueda (una por linea)", "palabras_clave_busqueda", 4),
            ("Palabras que acepta (una por linea)", "palabras_clave", 5),
            ("Palabras que descarta (una por linea)", "palabras_excluidas", 3),
        )
        cajas = {}
        for etiqueta, clave, alto in campos:
            tk.Label(marco, text=etiqueta, bg=COLORES["fondo"], anchor="w",
                     font=("Segoe UI", 9, "bold")).pack(fill="x", pady=(6, 1))
            caja = tk.Text(marco, height=alto, wrap="none", font=("Consolas", 9))
            caja.insert("1.0", "\n".join(cfg.get(clave) or []))
            caja.pack(fill="x")
            cajas[clave] = caja
        var_remoto = tk.BooleanVar(value=bool(cfg.get("incluir_remoto", True)))
        ttk.Checkbutton(marco, text="Incluir ofertas remotas sin importar la zona",
                        variable=var_remoto).pack(anchor="w", pady=(10, 0))

        def guardar():
            datos = cargar_config()
            for clave, caja in cajas.items():
                datos[clave] = [l.strip() for l in caja.get("1.0", "end").splitlines() if l.strip()]
            datos["incluir_remoto"] = bool(var_remoto.get())
            if not datos["zonas"] and not datos["incluir_remoto"]:
                messagebox.showwarning(
                    "Perfil",
                    "Deja al menos una zona o activa 'Incluir ofertas remotas'.",
                    parent=top,
                )
                return
            try:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(datos, f, ensure_ascii=False, indent=2)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el perfil: {e}", parent=top)
                return
            top.destroy()
            self.recargar()
            self.mensaje("Perfil guardado: la proxima busqueda usara estos datos.",
                         COLORES["verde"])

        barra = tk.Frame(top, bg=COLORES["fondo"], pady=10, padx=14)
        barra.pack(fill="x")
        ttk.Button(barra, text="Guardar", style="Verde.TButton", command=guardar).pack(side="left")
        ttk.Button(barra, text="Cancelar", command=top.destroy).pack(side="left", padx=(8, 0))

    def _correr_hilo(self, funcion, al_terminar=None):
        if self.trabajando:
            return
        self._ocupado(True)

        def trabajador():
            resultado = None
            error = None
            try:
                resultado = funcion()
            except Exception as e:
                error = e
            self.cola.put(("fin", resultado, error, al_terminar))

        threading.Thread(target=trabajador, daemon=True).start()
        self.raiz.after(120, self._procesar_cola)

    def _procesar_cola(self):
        try:
            while True:
                evento = self.cola.get_nowait()
                if evento[0] == "linea":
                    self.mensaje(evento[1])
                elif evento[0] == "fin":
                    _, resultado, error, al_terminar = evento
                    self._ocupado(False)
                    if error is not None:
                        messagebox.showerror("Error", f"Fallo la operacion: {error}")
                        self.mensaje(f"Error: {error}", COLORES["peligro"])
                    elif al_terminar:
                        al_terminar(resultado)
        except queue.Empty:
            pass
        if self.trabajando:
            self.raiz.after(150, self._procesar_cola)

    def accion_buscar(self):
        if self.trabajando:
            return
        self._ocupado(True)

        def trabajador():
            error = None
            codigo = None
            try:
                ruta_main = os.path.join(BASE, "main.py")
                proc = subprocess.Popen(
                    [python_consola(), ruta_main],
                    cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    encoding="utf-8", errors="replace",
                )
                for linea in proc.stdout:
                    linea = linea.strip()
                    if linea:
                        self.cola.put(("linea", linea[:130]))
                proc.wait()
                codigo = proc.returncode
            except Exception as e:
                error = e
            self.cola.put(("fin", codigo, error, self._fin_buscar))

        threading.Thread(target=trabajador, daemon=True).start()
        self.raiz.after(120, self._procesar_cola)

    def _fin_buscar(self, codigo):
        self.recargar()
        if codigo == 0:
            self.mensaje("Busqueda finalizada. Tabla actualizada.", COLORES["verde"])
        else:
            self.mensaje("La busqueda termino con errores (revisa la consola).", COLORES["peligro"])

    def accion_verificar(self):
        def verificar_directo():
            from verificar import verificar_ofertas

            retiradas, revisadas = verificar_ofertas(cargar_config())
            return retiradas, revisadas

        def al_terminar(resultado):
            retiradas, revisadas = resultado
            self.recargar()
            if retiradas:
                self.mensaje(
                    f"{len(retiradas)} oferta(s) ya no disponibles retiradas "
                    f"(revisadas {revisadas}).",
                    COLORES["verde"],
                )
            else:
                self.mensaje(
                    f"Verificadas {revisadas}: todas siguen disponibles.",
                    COLORES["verde"],
                )

        self._correr_hilo(verificar_directo, al_terminar)


def datetime_hoy():
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d")


def ejecutar():
    raiz = tk.Tk()
    Aplicacion(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    try:
        ejecutar()
    except Exception:
        import traceback

        try:
            registrar("ERROR app " + traceback.format_exc().replace("\n", " | "))
            messagebox.showerror("Error inesperado", traceback.format_exc()[-600:])
        except Exception:
            pass
        raise
