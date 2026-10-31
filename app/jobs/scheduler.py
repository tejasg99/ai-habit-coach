import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.jobs.reminders import run_once

logger = logging.getLogger(__name__)


def _safe_sweep() -> None:
    try:
        run_once()
    except Exception:
        logger.exception("Reminder sweep crashed")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _safe_sweep,
        "interval",
        minutes=settings.REMINDER_SWEEP_MINUTES,
        id="reminder_sweep",  # a stable id, so restarts never create duplicate jobs
        max_instances=1,  # never run two sweeps at once in this process
        coalesce=True,  # if runs were missed, run once, not once per missed slot
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: sweep every %s minutes", settings.REMINDER_SWEEP_MINUTES)
    return scheduler
