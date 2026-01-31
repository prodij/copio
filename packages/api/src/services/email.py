"""Email service for sending templated emails.

For now, this logs emails to console. Later, it can be swapped for
SMTP, SendGrid, SES, or any other email provider.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Jinja2 environment
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


class EmailService:
    """Email service for sending templated emails."""

    def __init__(self, backend: str = "console"):
        """
        Initialize email service.
        
        Args:
            backend: Email backend to use. Options:
                - "console": Log emails to console (default, for development)
                - "smtp": Send via SMTP (not yet implemented)
                - "sendgrid": Send via SendGrid (not yet implemented)
                - "ses": Send via AWS SES (not yet implemented)
        """
        self.backend = backend
        self._smtp_config: dict[str, Any] = {}

    def configure_smtp(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        from_email: str = "noreply@copio.app",
        from_name: str = "Copio",
    ) -> None:
        """Configure SMTP settings for when SMTP backend is used."""
        self._smtp_config = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "use_tls": use_tls,
            "from_email": from_email,
            "from_name": from_name,
        }

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render an email template with context."""
        # Add common context variables
        context.setdefault("year", datetime.now().year)
        
        template = jinja_env.get_template(template_name)
        return template.render(**context)

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        template: str,
        context: dict[str, Any],
    ) -> bool:
        """
        Send a templated email.
        
        Args:
            to: Recipient email address(es)
            subject: Email subject line
            template: Template filename (e.g., "registration_verification.html")
            context: Template context variables
            
        Returns:
            True if email was sent successfully
        """
        recipients = [to] if isinstance(to, str) else to
        context["subject"] = subject
        
        html_content = self._render_template(template, context)
        
        if self.backend == "console":
            return await self._send_console(recipients, subject, html_content, context)
        elif self.backend == "smtp":
            return await self._send_smtp(recipients, subject, html_content)
        else:
            logger.error(f"Unknown email backend: {self.backend}")
            return False

    async def _send_console(
        self,
        recipients: list[str],
        subject: str,
        html_content: str,
        context: dict[str, Any],
    ) -> bool:
        """Log email to console (development mode)."""
        logger.info("=" * 60)
        logger.info("📧 EMAIL (Console Backend)")
        logger.info("=" * 60)
        logger.info(f"To: {', '.join(recipients)}")
        logger.info(f"Subject: {subject}")
        logger.info("-" * 60)
        
        # Log key context variables (useful for development)
        for key in ["verification_url", "reset_url", "invite_url", "code"]:
            if key in context:
                logger.info(f"{key}: {context[key]}")
        
        logger.info("-" * 60)
        logger.info("HTML content rendered successfully")
        logger.info("=" * 60)
        
        return True

    async def _send_smtp(
        self,
        recipients: list[str],
        subject: str,
        html_content: str,
    ) -> bool:
        """Send email via SMTP (placeholder for future implementation)."""
        # TODO: Implement SMTP sending
        # This would use aiosmtplib for async SMTP
        logger.warning("SMTP backend not yet implemented, falling back to console")
        return await self._send_console(recipients, subject, html_content, {})


# Singleton instance
email_service = EmailService()


# Convenience functions for common email types
async def send_verification_email(
    to: str,
    first_name: str | None,
    verification_url: str,
    expires_in_hours: int = 24,
) -> bool:
    """Send email verification email."""
    return await email_service.send_email(
        to=to,
        subject="Verify your email address - Copio",
        template="registration_verification.html",
        context={
            "first_name": first_name,
            "verification_url": verification_url,
            "expires_in_hours": expires_in_hours,
        },
    )


async def send_password_reset_email(
    to: str,
    first_name: str | None,
    reset_url: str,
    expires_in_hours: int = 1,
) -> bool:
    """Send password reset email."""
    return await email_service.send_email(
        to=to,
        subject="Reset your password - Copio",
        template="password_reset.html",
        context={
            "first_name": first_name,
            "reset_url": reset_url,
            "expires_in_hours": expires_in_hours,
        },
    )


async def send_two_factor_code_email(
    to: str,
    first_name: str | None,
    code: str,
    expires_in_minutes: int = 10,
) -> bool:
    """Send two-factor authentication code email."""
    return await email_service.send_email(
        to=to,
        subject="Your verification code - Copio",
        template="two_factor_code.html",
        context={
            "first_name": first_name,
            "code": code,
            "expires_in_minutes": expires_in_minutes,
        },
    )


async def send_invite_email(
    to: str,
    tenant_name: str,
    inviter_name: str,
    inviter_email: str,
    role: str,
    invite_url: str,
    message: str | None = None,
    expires_in_days: int = 7,
) -> bool:
    """Send user invitation email."""
    return await email_service.send_email(
        to=to,
        subject=f"You're invited to join {tenant_name} on Copio",
        template="invite_user.html",
        context={
            "tenant_name": tenant_name,
            "inviter_name": inviter_name,
            "inviter_email": inviter_email,
            "role": role,
            "invite_url": invite_url,
            "message": message,
            "expires_in_days": expires_in_days,
        },
    )
