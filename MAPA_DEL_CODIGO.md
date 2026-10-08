# Mapa del código

Guía para entender qué hace cada archivo y en qué orden se ejecuta todo.
Léela con el README al lado: aquí está el **cómo**, allá el **qué**.

## Vista general

```
                        ┌──────────────────────────────┐
                        │  config.json  (tu perfil)    │
                        │  zonas, palabras, dias...    │
                        └──────────────┬───────────────┘
                                       │ se lee al inicio
                                       ▼
 8:00 am ──► buscar.cmd ──► main.py :: main()
                                   │
               ┌───────────────────┼────────────────────┐
               ▼                   ▼                    ▼
        1. purgar_ofertas    2. recolectar        3. pasa_filtros
           (retira >15 dias)     │                   (zonas+palabras)
                                 ▼
                    ┌────────────────────────┐
                    │ fuentes/*.py (4 sitios)│
                    │ computrabajo           │
                    │ trabajo_org            │
                    │ findjob24h             │
                    │ linkedin               │
                    └────────────────────────┘
                                 │
               4. escribir_csv (nuevas) ──► data/ofertas.csv
               5. verificar.py (ofertas cerradas → lista negra)
               6. escribir_reporte ──► data/reporte.html
               7. toast / correo / historial.log

 usuario ──► Abrir Ofertas.cmd ──► app.pyw (ventana Tkinter)
                                        │
                                        ├─ Botón "Buscar ahora" ──► subprocess main.py
                                        ├─ Botón "Verificar"     ──► subprocess verificar.py
                                        ├─ Botón "Eliminar"      ──► eliminar_ofertas()  (misma lógica que main)
                                        ├─ Botón "Editar perfil" ──► escribe config.json
                                        ├─ Botón "Lista negra"   ──► restaurar entradas
                                        ├─ Botón "Estadísticas"  ──► calcular_estadisticas() (resumen)
                                        └─ "Auto cada N min"     ──► raiz.after → busca sola (app_auto_minutos)

 tests/ ──► python -m unittest discover -s tests      .github/workflows/ci.yml ──► CI en cada push
```

## Archivo por archivo

| Archivo | Qué hace | Funciones clave |
|---|---|---|
| `main.py` | El cerebro: config, datos, filtros y la corrida completa | `main`, `pasa_filtros`, `recolectar`, `eliminar_ofertas`, `pasar_a_lista_negra` |
| `app.pyw` | Ventana de escritorio; llama a las mismas funciones de `main` | `Aplicacion._construir`, `pintar`, `accion_*`, `_correr_hilo` |
| `verificar.py` | Detecta ofertas cerradas y las retira (solo con evidencia) | `obtener`, `estado_oferta`, `verificar_ofertas` |
| `eliminar.py` | Borrado por terminal (menú o `--dias N`) | `purgar`, `menu`, `main` |
| `notificar.py` | Toast de Windows y correo SMTP (opcional) | `toast`, `enviar_correo` |
| `fuentes/comun.py` | Utilidades compartidas de descarga (con reintentos) | `descargar`, `fetch`, `pausar`, `sin_acentos` |
| `fuentes/computrabajo.py` | Busca en cr.computrabajo.com | `buscar` |
| `fuentes/trabajo_org.py` | Busca en trabajo.org.cr | `buscar` |
| `fuentes/findjob24h.py` | Busca en findjob24h.com | `buscar` |
| `fuentes/linkedin.py` | Endpoint público de invitados de LinkedIn | `buscar` |
| `tests/` | Pruebas unitarias (unittest, sin instalar nada) | `test_main`, `test_verificar`, `test_app_helpers` |
| `.github/workflows/ci.yml` | CI: compila y corre las pruebas en Windows con Python 3.12 | — |
| `docs/` | Capturas de la aplicación que ves en el README | — |
| `config.json` | Tu perfil: zonas, palabras, dias (no se sube a GitHub) | — |
| `config.example.json` | Plantilla que se copia al primer arranque | — |

Cada fuente expone **la misma interfaz**: `buscar(cfg) → [ofertas]` con claves
`titulo, ubicacion, empresa, url, fuente`. Por eso `recolectar` puede llamar a
las 4 sin importar de cuál venga cada oferta.

## El flujo de `main()` (main.py, línea por línea)

1. **`asegurar_config` / `cargar_config`** — lee tu perfil.
2. **`purgar_ofertas(dias)`** — saca del CSV lo viejo (los borrados pasan a lista negra).
3. **`recolectar(cfg)`** — consulta las 4 fuentes (`fuentes/*.py::buscar`).
4. **`pasa_filtros(oferta, zonas, cfg)`** — ¿excluida? ¿palabra clave? ¿zona o remoto?
5. **Deduplicar** — descarta lo que esté en `vistas.json`, `lista_negra.json` o ya en el CSV.
6. **`escribir_csv(nuevas)`** — agrega las nuevas al CSV.
7. **`verificar_ofertas(cfg)`** (si `verificar_en_busqueda`) — mira ofertas viejas: si están
   cerradas (fecha vencida, 404/410, "ya no se aceptan solicitudes"), las retira.
8. **`escribir_reporte`** — regenera `reporte.html` (solo lectura).
9. **`guardar_vistas` + `registrar`** — marca vistas y escribe `historial.log`.
10. **Avisos** — `toast` de Windows y correo si `notificar_toast` / `correo.activo`.

## La clase `Aplicacion` (app.pyw)

- **`_construir`** — dibuja todo: encabezado con contadores, toolbar, filtros,
  tabla `Treeview` y pie de mensajes.
- **`pintar`** — aplica filtro + orden y repuebla la tabla (se llama sola cuando
  cambias texto/estado/orden).
- **`accion_*`** — una por botón; las lentas (buscar/verificar) corren en hilo vía
  **`_correr_hilo`**: Tk solo se toca desde el hilo principal, por eso los resultados
  vuelven por la **`cola`** y se procesan con `raiz.after` en `_procesar_cola`.
- **`accion_perfil`** — lee `config.json`, muestra 4 cajas de texto, guarda y `recargar()`.
- **`accion_estadisticas`** — ventana con `calcular_estadisticas()`: total, reparto por
  estado, ofertas nuevas de los últimos 7 días y conteo por fuente.
- **Búsqueda automática** — el `Checkbutton` del pie (`alternar_auto`) agenda
  `_auto_tick` con `raiz.after(app_auto_minutos × 60000)`; cada tic dispara
  `accion_buscar` si no hay trabajo en curso y vuelve a agendarse. La preferencia
  se guarda en `config.json` con `guardar_config_parcial`.

## Pruebas y CI

- **Dónde**: `tests/` — `test_main.py` (filtros, lista negra, purgas, reporte),
  `test_verificar.py` (`validthrough`, ID de Computrabajo, estados, corrida) y
  `test_app_helpers.py` (filtros de la ventana, estadísticas, config parcial).
  Todas redirigen rutas a un temporal: **nunca tocan tus datos reales**.
- **Cómo** (desde la raíz del proyecto): `python -m unittest discover -s tests -v`.
  Sin dependencias: se usa `unittest` de la biblioteca estándar.
- **CI**: `.github/workflows/ci.yml` corre lo mismo en Windows con Python 3.12 en
  cada push/PR; el badge del README lo refleja.

## Los archivos de datos (carpeta `data/`, no se sube a GitHub)

| Archivo | Contenido | Quién lo escribe |
|---|---|---|
| `ofertas.csv` | Filas: fecha;fuente;titulo;ubicacion;empresa;url;estado_envio | `main.py`, app (estados) |
| `lista_negra.json` | `{urls: {clave: {hasta, titulo, fuente}}}` — no volver a traer | `pasar_a_lista_negra` |
| `vistas.json` | Qué URLs ya se vieron y cuándo | `main()` |
| `reporte.html` | Visor de solo lectura | `escribir_reporte` |
| `historial.log` | Registro con fecha de todo lo que pasó | `registrar` |

## Si quieres cambiar algo, mira aquí

- **Otra zona o palabra** → botón *Editar perfil* (o `config.json`).
- **Que busque sola cada X minutos** → casilla *Auto cada N min* del pie (o `app_auto_minutos` en `config.json`; 0 = apagado).
- **Otra fuente de empleo** → nuevo archivo en `fuentes/` con `buscar(cfg)` + agregarlo a `FUENTES` en `main.py`.
- **El texto de los filtros** → `pasa_filtros` en `main.py`.
- **El aspecto de la ventana** → `COLORES` y `_construir` en `app.pyw`.
- **Cuándo se retira una oferta** → `estado_oferta` en `verificar.py`.
- **Cómo se prueba algo** → `tests/`; añade un caso nuevo y corre `python -m unittest discover -s tests -v`.
