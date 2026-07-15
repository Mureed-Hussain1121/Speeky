import os
from email.message import EmailMessage

import aiosmtplib


def _get_transport_config() -> dict:
    """Builds transport config from SMTP_HOST/PORT/USER/PASS/SECURE env vars (dev or prod)."""
    # nodemailer's `secure` option: true = implicit TLS from connect (aiosmtplib use_tls);
    # false = plain connect, upgrade to STARTTLS only if the server offers it (aiosmtplib's
    # start_tls=None, its default "opportunistic" mode) — NOT start_tls=True, which means
    # "require STARTTLS, hard-fail if unsupported" and has no nodemailer equivalent here.
    secure = os.environ.get("SMTP_SECURE") == "true"
    return {
        "hostname": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "username": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASS"),
        "use_tls": secure,
        "start_tls": None if not secure else False,
    }


async def send_password_reset_email(to: str, reset_url: str) -> None:
    cfg = _get_transport_config()
    ttl = os.environ.get("RESET_TOKEN_TTL_MINUTES", "15")

    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", '"Speeky AI" <no-reply@speeky.ai>')
    msg["To"] = to
    msg["Subject"] = "Reset your Speeky AI password"
    msg.set_content(
        f"You requested a password reset.\n\n"
        f"Click the link below (valid for {ttl} minutes):\n\n{reset_url}\n\n"
        f"If you did not request this, ignore this email."
    )
    msg.add_alternative(
        f"""
      <p>You requested a password reset.</p>
      <p>Click the link below (valid for <strong>{ttl} minutes</strong>):</p>
      <p><a href="{reset_url}">{reset_url}</a></p>
      <p>If you did not request this, ignore this email.</p>
    """,
        subtype="html",
    )

    await aiosmtplib.send(
        msg,
        hostname=cfg["hostname"],
        port=cfg["port"],
        username=cfg["username"],
        password=cfg["password"],
        use_tls=cfg["use_tls"],
        start_tls=cfg["start_tls"],
    )

    if os.environ.get("NODE_ENV") != "production":
        print(f"[DEV] Reset URL: {reset_url}")
