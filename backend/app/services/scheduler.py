from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app import database
from app.config import get_settings
from app.services.data_fetcher import sync_market_data
from app.services.push import push_report_to_miniapp_subscribers, push_report_to_wechat
from app.services.reports import generate_report, publish_report


def _run_report_job(session_name: str) -> None:
    db = database.SessionLocal()
    try:
        sync_market_data(db, job_type=f"scheduled-{session_name}", days=60)
        report = generate_report(db, session_name=session_name)
        published = publish_report(db, report.id)
        if published:
            push_report_to_wechat(db, published)
            push_report_to_miniapp_subscribers(db, published)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    if not get_settings().scheduler_enabled:
        return None
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(_run_report_job, "cron", args=["morning"], day_of_week="mon-fri", hour=8, minute=30, id="daily_morning")
    scheduler.add_job(_run_report_job, "cron", args=["evening"], day_of_week="mon-fri", hour=17, minute=30, id="daily_evening")
    scheduler.start()
    return scheduler
