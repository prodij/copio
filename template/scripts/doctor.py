"""`make doctor`: list app records that need attention (spec section 9). Exit 1 if any.

- workspaces stuck in `creating` for over 5 minutes (a retry of POST /workspaces resumes them),
- subscriptions `pending` for over a day (checkout never finished; billing_reconcile retries),
- Lago webhooks stored but never processed.
"""

import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, create_engine, select
from sqlalchemy.exc import SQLAlchemyError

STUCK_CREATING = timedelta(minutes=5)
STUCK_PENDING = timedelta(days=1)

meta = MetaData()
workspaces = Table(
    "workspaces", meta, Column("id", String), Column("name", String), Column("status", String),
    Column("created_at", DateTime(timezone=True)),
)
subscriptions = Table(
    "subscriptions", meta, Column("workspace_id", String), Column("plan_code", String),
    Column("state", String), Column("updated_at", DateTime(timezone=True)),
)
webhook_events = Table(
    "webhook_events", meta, Column("id", String), Column("type", String),
    Column("received_at", DateTime(timezone=True)), Column("processed_at", DateTime(timezone=True)),
)


def find_problems(engine: Engine, now: datetime) -> list[str]:
    problems: list[str] = []
    with engine.connect() as conn:
        for w in conn.execute(select(workspaces).where(
                workspaces.c.status == "creating", workspaces.c.created_at < now - STUCK_CREATING)):
            problems.append(f"workspace {w.id} ({w.name}) stuck in 'creating' since {w.created_at}")
        for s in conn.execute(select(subscriptions).where(
                subscriptions.c.state == "pending", subscriptions.c.updated_at < now - STUCK_PENDING)):
            problems.append(f"subscription of workspace {s.workspace_id} ({s.plan_code}) pending since {s.updated_at}")
        for e in conn.execute(select(webhook_events).where(webhook_events.c.processed_at.is_(None))):
            problems.append(f"webhook {e.id} ({e.type}) received {e.received_at} never processed")
    return problems


def database_url() -> str:
    return os.environ.get("DOCTOR_DATABASE_URL") or (
        f"postgresql+psycopg://app:app@127.0.0.1:{os.environ.get('POSTGRES_PORT') or 5432}/app"
    )


def main(url: str | None = None) -> int:
    engine = create_engine(url or database_url())
    try:
        problems = find_problems(engine, datetime.now(UTC))
    except SQLAlchemyError as exc:
        print(f"doctor: cannot read the app database ({type(exc).__name__}); is `make up` running "
              f"and have migrations run (`make migrate`)?", file=sys.stderr)
        return 2
    finally:
        engine.dispose()
    for problem in problems:
        print(problem)
    print("doctor: nothing stuck" if not problems else f"doctor: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
