"""Email dispatch utilities for auth flows (SendGrid / SES via SMTP)."""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from api_server.deps import Settings  # noqa: TC001 — used at runtime for type dispatch

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    settings: Settings,
) -> None:
    """Send an email via SMTP (SendGrid / SES).

    If SMTP is not configured (smtp_host is empty), logs a warning and
    returns silently — this lets the dev environment work without email.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_body: HTML body content.
        settings: Application settings with SMTP config.
    """
    if not settings.smtp_host:
        logger.warning("SMTP not configured — skipping email to %s: %s", to, subject)
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(html_body, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=587,
        username="apikey",
        password=settings.smtp_api_key,
        start_tls=True,
    )
    logger.info("Email sent to %s: %s", to, subject)


async def send_password_reset_email(
    to: str,
    token: str,
    settings: Settings,
) -> None:
    """Send a password reset email with a reset link.

    Args:
        to: Recipient email address.
        token: The password reset token.
        settings: Application settings.
    """
    reset_url = f"{settings.frontend_url}/reset-password/{token}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Reset your password</h2>
        <p>Click the link below to reset your Kutana password. This link expires in 1 hour.</p>
        <p><a href="{reset_url}" style="color: #16A34A; font-weight: bold;">Reset Password</a></p>
        <p style="color: #888; font-size: 12px;">If you didn't request this, you can safely ignore this email.</p>
    </div>
    """
    await send_email(to, "Reset your Kutana password", html, settings)


async def send_verification_email(
    to: str,
    token: str,
    settings: Settings,
) -> None:
    """Send an email verification link.

    Args:
        to: Recipient email address.
        token: The email verification token.
        settings: Application settings.
    """
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Verify your email</h2>
        <p>Welcome to Kutana! Please verify your email address by clicking the link below.</p>
        <p><a href="{verify_url}" style="color: #16A34A; font-weight: bold;">Verify Email</a></p>
        <p style="color: #888; font-size: 12px;">If you didn't create a Kutana account, you can safely ignore this email.</p>
    </div>
    """
    await send_email(to, "Verify your Kutana email", html, settings)
