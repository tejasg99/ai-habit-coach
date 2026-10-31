from app.core.config import settings
from app.jobs import reminders as reminders_job
from app.jobs.scheduler import start_scheduler


def test_cli_exits_zero_when_the_sweep_succeeds(monkeypatch):
    monkeypatch.setattr(reminders_job, "run_once", lambda: None)
    assert reminders_job.main() == 0


def test_cli_exits_non_zero_when_the_sweep_crashes(monkeypatch):
    def boom():
        raise RuntimeError("db is down")

    monkeypatch.setattr(reminders_job, "run_once", boom)
    assert reminders_job.main() == 1  # cron/CI systems use the exit code to notice failures


def test_scheduler_registers_one_stable_sweep_job():
    scheduler = start_scheduler()
    try:
        job = scheduler.get_job("reminder_sweep")
        assert job is not None
        assert job.trigger.interval.total_seconds() == settings.REMINDER_SWEEP_MINUTES * 60
    finally:
        scheduler.shutdown(wait=False)
