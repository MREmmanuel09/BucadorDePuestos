# Buscador de Puestos

Busca ofertas que coincidan con tu perfil (Soporte TI / Redes / Sistemas) en las zonas configuradas y te notifica.

## Uso diario (aplicacion)

- **Icono del escritorio "Mis Ofertas"** (o doble clic en `Abrir Ofertas.cmd`): abre la aplicacion
  para ver las ofertas, eliminar (lista negra 15 dias), marcar estados, buscar y verificar
  disponibilidad. No necesita servidor ni conexion especial: siempre funciona.
- **Editar perfil**: cambiar zonas, terminos de busqueda y palabras aceptadas/excluidas
  desde la ventana de la app (guarda en `config.json`).
- Doble clic en una fila abre la oferta en el navegador.
- `buscar.cmd` solo ejecuta la busqueda sin abrir la app (para corridas manuales/rapidas).

## Que hace cada ejecucion

1. Consulta 4 fuentes publicas: Computrabajo, Trabajo.org, FindJob24h y LinkedIn (endpoint publico de invitados).
2. Filtra por palabras de TI y por zona (las de tu perfil en `config.json`) o remoto.
3. Descarta ofertas ya vistas (`buscador\data\vistas.json`) y las que estan en lista negra (`buscador\data\lista_negra.json`, vigencia de `dias_lista_negra`).
4. Borra automaticamente las ofertas con mas de `dias_retencion` dias (por defecto 15; las marcadas con `estado_envio` se conservan) y las mueve a la lista negra.
5. Agrega las nuevas a `buscador\data\ofertas.csv` (abrelo con Excel, separador `;`).
6. **Verifica si las ofertas siguen disponibles** (`verificar.py`): si una pagina dice "ya no se aceptan solicitudes", "oferta finalizada", responde 404/410, perdio su ID o su `validthrough` vencio, la retira del CSV y la pone en lista negra. Solo con evidencia positiva: un error de red nunca borra nada.
7. Genera `buscador\data\reporte.html` (visor de solo lectura).
8. Muestra una notificacion de Windows si hay ofertas nuevas.

## Configuracion

En el primer arranque se crea `buscador\config.json` a partir de
`buscador\config.example.json` (la plantilla versionada en Git). Lo mas comun es
editar el perfil desde la aplicacion; las claves manuales son:

- `palabras_clave_busqueda`: terminos que se consultan en las fuentes.
- `palabras_clave`: palabras que debe tener el titulo/ubicacion para aceptar (soporte, redes, help desk, cableado, M365, n1...).
- `palabras_excluidas`: rechazo automatico (ventas, comercial, programador, marketing, contabilidad...).
- `palabras_remoto`: palabras que marcan una oferta como remota.
- `zonas`: zonas aceptadas.
- `incluir_remoto`: acepta teletrabajo sin importar la zona.
- `dias_retencion`: dias antes de que una oferta se borre sola del CSV (defecto 15; pon 7 para una semana).
- `dias_lista_negra`: dias que una oferta eliminada no puede volver a aparecer (defecto 15).
- `verificar_en_busqueda`: activa la deteccion de ofertas cerradas en cada corrida (defecto true).
- `verificar_max_por_corrida`: cuantas ofertas viejas se revisan por corrida (defecto 30).
- `max_detalles_findjob24h`: cuantas ofertas de FindJob24h se verifican (mas = mas lento).
- `notificar_toast`: notificacion de Windows.
- `abrir_reporte`: abrir `reporte.html` automaticamente cuando hay ofertas nuevas.
- `correo`: para recibir el aviso por email, activar y llenar con una clave de aplicacion de Gmail.

## Aplicacion (`buscador\app.pyw`)

- **Buscar ahora**: corre la busqueda completa y actualiza la tabla (barra de estado con el progreso).
- **Verificar disponibilidad**: revisa las ofertas viejas y retira las que ya no existen.
- **Eliminar seleccionadas**: confirma y borra del CSV + lista negra 15 dias (con titulo y fuente guardados).
- **Lista negra**: ventana con lo que esta oculto, fecha de expiracion y boton para restaurar.
- **Marcar**: pone "Postulado"/"Descartado" (o vacio) en la seleccion.
- **Editar perfil**: zonas, terminos de busqueda, palabras aceptadas/excluidas y si
  incluir remotas; se aplica en la proxima busqueda.
- **Seleccionar Todo/Ninguno** y orden por fecha (mas nuevos / mas viejos).
- **Filtro en vivo** por texto y por estado; doble clic abre la oferta.
- `reporte.html` es un visor de solo lectura (la gestion es en la app).

## Borrar ofertas (evitar cola infinita)

- **Manual (app):** seleccionar y *Eliminar seleccionadas* → entra a `lista_negra.json` por
  `dias_lista_negra` dias: el sistema no la vuelve a traer como nueva en ese plazo.
- **Automatico:** cada corrida purga del CSV las ofertas con mas de `dias_retencion` dias (y las
  mueve a la lista negra); las marcadas con `estado_envio` no se purgan por antiguedad.
- **Cerradas:** el verificador retira sola las ofertas finalizadas/cerradas (ver paso 6).
- **Terminal (avanzado):** `python buscador\eliminar.py` (purga 7/15 dias o por numeros) o
  `python buscador\verificar.py` (solo verificacion).

## Programar una vez al dia (8:00 am)

Ejecutar una vez en PowerShell:

```
schtasks /Create /TN "BuscadorPuestos" /TR "\"D:\Proyectos\BucadorDePuestos\buscar.cmd\"" /SC DAILY /ST 08:00
```

Para probar: `schtasks /Run /TN "BuscadorPuestos"`
Para eliminar: `schtasks /Delete /TN "BuscadorPuestos" /F`

## Limitaciones conocidas

- Algunos portales (ej. Gente Coyol) requieren inicio de sesion: revisarlos manualmente.
- LinkedIn se consulta por su endpoint publico de invitados; puede cambiar o bloquearse sin aviso. Respaldo: activar alertas de empleo por correo en LinkedIn.
- Las zonas se amplian desde **Editar perfil** en la aplicacion.
- Uso personal, las fuentes son publicas y se consultan con pausas entre solicitudes.
