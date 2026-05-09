"""Inngest setup.

Phase 1.0 wires Inngest as the worker queue infrastructure but doesn't put
the diagnostic on the hot path through it (streaming back through Inngest
adds complexity that Phase 1.0 doesn't need). Used here for:

  - Async memory writes after a diagnostic completes
  - Hook for the Phase 1.1 nightly eval cron
  - Hook for the Phase 1.1 reaction -> eval-signal pipeline

The diagnostic itself runs inline through the FastAPI streaming endpoint.
"""
from __future__ import annotations

from typing import Any

import inngest
from fastapi import APIRouter

from copio_api.config import get_settings
from copio_api.logging import get_logger

log = get_logger(__name__)
_settings = get_settings()

inngest_client = inngest.Inngest(
    app_id="copio-api",
    is_production=not _settings.is_dev,
    event_key=_settings.inngest_event_key,
    signing_key=_settings.inngest_signing_key,
)


@inngest_client.create_function(
    fn_id="diagnostic-completed",
    trigger=inngest.TriggerEvent(event="diagnostic/completed"),
)
async def on_diagnostic_completed(ctx: inngest.Context) -> dict[str, Any]:
    """Phase 1.0 stub: log + return. Phase 1.1 fans out to:
      - reaction polling
      - eval-signal aggregation
      - memory consolidation
    """
    log.info("inngest.diagnostic_completed", payload=ctx.event.data)
    return {"ok": True, "event": ctx.event.data}


FUNCTIONS = [on_diagnostic_completed]


def register_functions(router: APIRouter, *, client: inngest.Inngest) -> Any:
    try:
        from inngest.fast_api import serve

        serve(router, client, FUNCTIONS)
    except (ImportError, AttributeError) as exc:
        log.warning("inngest.serve_unavailable", reason=str(exc))
    return router
