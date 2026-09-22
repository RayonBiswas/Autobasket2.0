"""Outbound email (sign-in codes). Plain SMTP with STARTTLS so any provider works; fails soft with a log line."""

import logging
import smtplib
from email.message import EmailMessage

from ..core.config import get_settings

log = logging.getLogger("autobasket.email")


def send_email(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not s.email_enabled:
        return False
    msg = EmailMessage()
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
        return True
    except Exception as exc:  # fail soft: the caller decides how to tell the user
        log.warning("email to %s failed: %s", to, exc)
        return False
