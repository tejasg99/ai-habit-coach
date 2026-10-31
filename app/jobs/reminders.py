import logging
import sys
from datetime import datetime, timezone

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.reminders import SweepStats, run_reminder_sweep

logger = logging.getLogger(__name__)


def run_once(now: datetime | None = None) -> SweepStats:
    with SessionLocal() as db:
        stats = run_reminder_sweep(db, now or datetime.now(timezone.utc))
    logger.info("Reminder sweep finished: %s", stats)
    return stats


def main() -> int:
    """Entry point for cron-style runners: `python -m app.jobs.reminders`."""
    configure_logging()
    try:
        run_once()
    except Exception:
        logger.exception("Reminder sweep crashed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
