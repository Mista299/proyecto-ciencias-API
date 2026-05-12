import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config

logger = logging.getLogger(__name__)

_BRAND = "#2E5339"
_LIME  = "#C5D86D"


def _base_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f7f5ee;font-family:system-ui,sans-serif">
<div style="max-width:480px;margin:32px auto;padding:0 16px">
  <div style="background:{_BRAND};border-radius:10px 10px 0 0;padding:24px 28px">
    <span style="color:{_LIME};font-size:20px;font-weight:700">✦ MUA Biodiversidad</span>
    <p style="color:#8FB996;font-size:12px;margin:4px 0 0">Sistema de gestión de colecciones · Universidad de Antioquia</p>
  </div>
  <div style="background:#fff;border-radius:0 0 10px 10px;padding:28px;border:1px solid #e3dfce;border-top:none">
    {body}
  </div>
</div>
</body></html>"""


def send_email(to: str, subject: str, html: str) -> None:
    if not config.SMTP_HOST or not config.SMTP_USER:
        logger.warning("SMTP not configured — skipping email to %s", to)
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = config.SMTP_FROM
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(config.SMTP_USER, config.SMTP_PASSWORD)
            srv.sendmail(config.SMTP_FROM, [to], msg.as_string())
    except Exception:
        logger.exception("Failed to send email to %s", to)


def send_credentials_email(to: str, username: str, password: str, verify_url: str) -> None:
    body = f"""
    <h2 style="color:#1c2620;font-size:18px;margin:0 0 8px">Bienvenido, {username}</h2>
    <p style="color:#4a544c;font-size:14px;margin:0 0 20px">Tu cuenta ha sido creada. Estas son tus credenciales de acceso:</p>
    <div style="background:#f7f5ee;border:1px solid #e3dfce;border-radius:8px;padding:20px;margin-bottom:20px">
      <p style="margin:0 0 4px;font-size:11px;color:#7e8479;text-transform:uppercase;letter-spacing:.5px">Usuario</p>
      <p style="margin:0 0 16px;font-size:15px;font-weight:700;color:#1c2620;font-family:monospace">{username}</p>
      <p style="margin:0 0 4px;font-size:11px;color:#7e8479;text-transform:uppercase;letter-spacing:.5px">Contraseña temporal</p>
      <p style="margin:0;font-size:15px;font-weight:700;color:#1c2620;font-family:monospace">{password}</p>
    </div>
    <p style="color:#4a544c;font-size:14px;margin:0 0 16px">Verifica tu correo para activar tu cuenta:</p>
    <a href="{verify_url}" style="display:inline-block;background:{_LIME};color:#1f3a27;font-weight:700;font-size:13px;padding:11px 22px;border-radius:7px;text-decoration:none">Verificar correo electrónico →</a>
    <p style="color:#7e8479;font-size:11px;margin:20px 0 0">Este enlace expira en 48 horas. Guarda tu contraseña temporal antes de verificar.</p>
    """
    send_email(to, "Bienvenido a MUA Biodiversidad — tus credenciales", _base_html(body))


def send_reset_email(to: str, username: str, reset_url: str) -> None:
    body = f"""
    <h2 style="color:#1c2620;font-size:18px;margin:0 0 8px">Recuperar contraseña</h2>
    <p style="color:#4a544c;font-size:14px;margin:0 0 20px">Hola <strong>{username}</strong>, recibimos una solicitud para restablecer tu contraseña.</p>
    <a href="{reset_url}" style="display:inline-block;background:{_LIME};color:#1f3a27;font-weight:700;font-size:13px;padding:11px 22px;border-radius:7px;text-decoration:none">Restablecer contraseña →</a>
    <p style="color:#7e8479;font-size:11px;margin:20px 0 0">Este enlace expira en 1 hora. Si no solicitaste esto, puedes ignorar este correo.</p>
    """
    send_email(to, "Recuperación de contraseña — MUA Biodiversidad", _base_html(body))
