import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from croniter import croniter

from jobs.runner import run

SCHEDULES = Path(__file__).resolve().parents[1] / "schedules.yaml"
log = logging.getLogger("jobs.scheduler")


@dataclass(frozen=True)
class Schedule:
    name: str
    cron: str


def load_schedules(path: Path = SCHEDULES) -> list[Schedule]:
    raw = yaml.safe_load(path.read_text()) or {}
    return [Schedule(str(s["job"]), str(s["cron"])) for s in raw.get("schedules", [])]


def due(schedules: list[Schedule], now: datetime, last_run: dict[str, datetime]) -> list[str]:
    """Jobs whose latest cron slot at or before `now` has not run yet (at most once per slot)."""
    names = []
    for s in schedules:
        slot = croniter(s.cron, now).get_prev(datetime)
        last = last_run.get(s.name)
        if last is None or last < slot:
            names.append(s.name)
    return names


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    schedules = load_schedules()
    last_run: dict[str, datetime] = {}
    while True:
        now = datetime.now(UTC)
        for name in due(schedules, now, last_run):
            last_run[name] = now
            try:
                log.info("%s %s", name, run(name, {}))
            except Exception:  # one failing job must not stop the scheduler
                log.exception("%s failed", name)
        time.sleep(30)


if __name__ == "__main__":
    main()
