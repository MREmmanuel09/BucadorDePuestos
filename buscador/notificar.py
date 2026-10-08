import base64
import smtplib
import ssl
import subprocess
from email.message import EmailMessage


def toast(titulo, mensaje):
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
    codificado = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-EncodedCommand", codificado],
        creationflags=0x08000000,
    )


def enviar_correo(correo_cfg, asunto, cuerpo_html):
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
