from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings


def smtp_ready() -> bool:
    return bool((settings.smtp_host or "").strip() and (settings.smtp_user or "").strip() and (settings.smtp_password or "").strip())


def send_text_email(*, to: str, subject: str, body: str) -> None:
    sender = (settings.smtp_from or settings.smtp_user or to).strip()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body or "")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
