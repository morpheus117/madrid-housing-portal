"""
APScheduler background task scheduler.

Runs inside the same process as the web server.  Jobs:
  - Daily  06:00 Europe/Madrid: update INE data
  - Weekly Mon 02:00 Europe/Madrid: full pipeline update + forecast refresh

Scheduler is only started when settings.scheduler_enabled is True.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.config import settings
from app.data.pipeline import DataPipeline
from app.services.forecasting import ForecastingService

_scheduler: BackgroundScheduler | None = None


def _daily_ine_update() -> None:
    logger.info("Scheduler: running daily INE update …")
    try:
        p = DataPipeline()
        p.update_ine_ipv()
        p.update_ine_mortgages()
        logger.info("Scheduler: daily INE update complete.")
    except Exception as exc:
        logger.error(f"Scheduler: daily INE update failed: {exc}")


def _weekly_full_update() -> None:
    logger.info("Scheduler: running weekly full update …")
    try:
        p = DataPipeline()
        p.run_full_update()
        ForecastingService().forecast_all_districts(periods=8)
        logger.info("Scheduler: weekly full update complete.")
    except Exception as exc:
        logger.error(f"Scheduler: weekly update failed: {exc}")


def start_scheduler() -> None:
    """Start the background scheduler (idempotent)."""
    global _scheduler

    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false).")
        return

    if _scheduler and _scheduler.running:
        logger.debug("Scheduler already running.")
        return

    tz = settings.scheduler_timezone
    _scheduler = BackgroundScheduler(timezone=tz)

    # Daily update — 06:00 local time
    _scheduler.add_job(
        _daily_ine_update,
        trigger=CronTrigger(hour=6, minute=0, timezone=tz),
        id="daily_ine_update",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Weekly full update — Monday 02:00 local time
    _scheduler.add_job(
        _weekly_full_update,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=0, timezone=tz),
        id="weekly_full_update",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started (tz={tz}). "
        "Jobs: daily INE @ 06:00, weekly full @ Mon 02:00."
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
