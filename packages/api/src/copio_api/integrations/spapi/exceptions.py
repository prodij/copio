"""Named SP-API exceptions per the Error & Rescue Map.

Critical rule from CEO plan: NO `except Exception:` blocks anywhere in the
agent runtime. Every catch must be for a named class. Every rescue either
retries with backoff, degrades gracefully with a user-visible message, or
re-raises with added context.
"""


class SPAPIError(Exception):
    """Base for all SP-API integration errors. Never raised directly."""

    def __init__(self, message: str, *, endpoint: str | None = None, status: int | None = None):
        super().__init__(message)
        self.endpoint = endpoint
        self.status = status


class SPAPIRateLimit(SPAPIError):
    """SP-API returned 429 (rate limited). Caller backs off + retries."""


class SPAPIAuthExpired(SPAPIError):
    """LWA access token expired. Caller refreshes via stored refresh token."""


class SPAPIUpstreamDown(SPAPIError):
    """SP-API endpoint returned 5xx. Caller falls back to cache."""


class SPAPIBadResponse(SPAPIError):
    """SP-API returned malformed/unexpected JSON. Caller falls back to cache."""


class SPAPIPermissionDenied(SPAPIError):
    """Tenant lacks scope for this endpoint. Surface re-grant link to CEO."""


class SPAPINotConfigured(SPAPIError):
    """No LWA token stored for this tenant. Surface onboarding."""
