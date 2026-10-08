"""Avisos al usuario: notificaciones de Windows y correo SMTP.

toast() muestra un aviso de escritorio vía PowerShell y enviar_correo()
envía un correo HTML por SMTP SSL con clave de aplicación de Gmail.
"""

import base64
import smtplib
import ssl
import subprocess
from email.message import EmailMessage


def toast(titulo, mensaje):
    """Muestra una notificación de Windows (aviso de escritorio).

    Recibe título y mensaje; lanza PowerShell en segundo plano sin bloquear
    y no devuelve nada.
    """
    # escapa comillas simples para que no rompan el literal de PowerShell
    limpio_t = titulo.replace("'", "''")
    limpio_m = mensaje.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f"$n.ShowBalloonTip(12000, '{limpio_t}', '{limpio_m}', [System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Seconds 14; "
        "$n.Dispose()"
    )
    # -EncodedCommand exige UTF-16LE en base64; Popen en segundo plano
    codificado = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-EncodedCommand", codificado],
        creationflags=0x08000000,
    )


def enviar_correo(correo_cfg, asunto, cuerpo_html):
    """Envía un correo HTML por SMTP SSL (Gmail con clave de aplicación).

    Recibe la configuración de correo, el asunto y el cuerpo HTML; devuelve
    True si se envió o False si no está configurado, sin lanzar errores.
    """
    if not correo_cfg.get("activo"):
        return False
    usuario = correo_cfg.get("usuario", "")
    clave = correo_cfg.get("clave_app", "")
    destino = correo_cfg.get("destino", "") or usuario
    if not usuario or not clave:
        return False
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = usuario
    msg["To"] = destino
    msg.set_content("Revisa el reporte del buscador de puestos.")
    msg.add_alternative(cuerpo_html, subtype="html")
    contexto = ssl.create_default_context()
    with smtplib.SMTP_SSL(correo_cfg.get("smtp", "smtp.gmail.com"), int(correo_cfg.get("puerto", 465)), context=contexto) as servidor:
        servidor.login(usuario, clave)
        servidor.send_message(msg)
    return True
