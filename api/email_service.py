"""
Email Service - Configurable email sending for auth flows.

Supports SMTP (production) and logging-only (development) modes.
Set EMAIL_PROVIDER=smtp and configure SMTP_* env vars for production.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from shared.logger import setup_logging

logger = setup_logging("email-service")

# Configuration from environment
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "log")  # "smtp" or "log"
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@clilens.ai")
FROM_NAME = os.getenv("FROM_NAME", "CliLens.AI")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5300")


def _send_smtp(to_email: str, subject: str, html_body: str):
    """Send email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_USE_TLS:
            server.starttls()
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())


def send_email(to_email: str, subject: str, html_body: str):
    """Send an email using the configured provider."""
    if EMAIL_PROVIDER == "smtp":
        try:
            _send_smtp(to_email, subject, html_body)
            logger.info("Email sent via SMTP", to=to_email, subject=subject)
        except Exception as e:
            logger.error("SMTP send failed", to=to_email, error=str(e))
            raise
    else:
        # Log-only mode for development
        logger.info(
            "Email (log mode)",
            to=to_email,
            subject=subject,
            body_preview=html_body[:200],
        )


def send_verification_email(to_email: str, token: str, full_name: str = ""):
    """Send email verification link."""
    verify_url = f"{FRONTEND_URL}/verify-email?token={token}"
    greeting = f"Hi {full_name}," if full_name else "Hi,"

    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #0d9488;">CliLens.AI - Verify Your Email</h2>
        <p>{greeting}</p>
        <p>Please verify your email address by clicking the button below:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}"
               style="background: #0d9488; color: white; padding: 12px 32px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                Verify Email
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            Or copy this link: <a href="{verify_url}">{verify_url}</a>
        </p>
        <p style="color: #999; font-size: 12px;">This link expires in 24 hours.</p>
    </div>
    """
    send_email(to_email, "Verify your CliLens.AI email", html)


def send_password_reset_email(to_email: str, token: str):
    """Send password reset link."""
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"

    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #0d9488;">CliLens.AI - Password Reset</h2>
        <p>You requested a password reset. Click the button below to set a new password:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}"
               style="background: #0d9488; color: white; padding: 12px 32px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                Reset Password
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            Or copy this link: <a href="{reset_url}">{reset_url}</a>
        </p>
        <p style="color: #999; font-size: 12px;">
            This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
        </p>
    </div>
    """
    send_email(to_email, "Reset your CliLens.AI password", html)
