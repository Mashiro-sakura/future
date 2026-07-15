from __future__ import annotations

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import database
from app.config import get_settings
from app.models import FuturesPrice
from app.routers import admin, auth, public
from app.seed import seed_database
from app.services.data_fetcher import sync_market_data
from app.services.reports import generate_report, publish_report
from app.services.scheduler import start_scheduler


def bootstrap_database() -> None:
    database.init_db()
    db = database.SessionLocal()
    try:
        seed_database(db)
        settings = get_settings()
        has_prices = db.query(FuturesPrice).first() is not None
        if settings.bootstrap_sample_data and not has_prices:
            sync_market_data(db, job_type="bootstrap", days=45)
            report = generate_report(db, session_name="evening")
            publish_report(db, report.id)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_database()
    scheduler = start_scheduler()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


app = FastAPI(title=get_settings().app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(public.router)

# ── 生产环境：FastAPI 同时托管前端 H5 页面 ──────────────────────────────
_H5_DIR = Path(__file__).resolve().parents[1] / "static"
if _H5_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_H5_DIR), html=True), name="h5")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
