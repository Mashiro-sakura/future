from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product, PushLog, Recommendation, Report, SyncLog
from app.routers.deps import get_current_admin
from app.schemas import ImportOut, LogsOut, PolicyEventCreate, PolicyEventCreateOut, ProductOut, PushOut, ReportOut, ReportUpdate, SyncOut
from app.services.data_fetcher import import_spot_csv, sync_market_data
from app.services.policy_events import create_policy_event
from app.services.push import push_report_to_miniapp_subscribers, push_report_to_wechat
from app.services.reports import generate_report, publish_report

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)) -> list[Product]:
    return db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.display_order).all()


@router.post("/data/sync", response_model=SyncOut)
def sync_data(days: int = 60, db: Session = Depends(get_db)) -> SyncOut:
    synced, message = sync_market_data(db, job_type="manual", days=days)
    return SyncOut(status="success" if synced else "failed", synced_products=synced, message=message)


@router.post("/import/spot", response_model=ImportOut)
async def import_spot(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportOut:
    try:
        imported, message = import_spot_csv(db, await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportOut(status="success", imported=imported, message=message)


@router.post("/reports/generate", response_model=ReportOut)
def generate(session_name: str = "evening", db: Session = Depends(get_db)) -> Report:
    return generate_report(db, session_name=session_name)


@router.get("/reports", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db)) -> list[Report]:
    return db.query(Report).order_by(desc(Report.generated_at)).limit(30).all()


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report


@router.patch("/reports/{report_id}", response_model=ReportOut)
def update_report(report_id: int, payload: ReportUpdate, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if payload.title is not None:
        report.title = payload.title
    if payload.market_summary is not None:
        report.market_summary = payload.market_summary
    if payload.price_behavior_analysis is not None:
        report.price_behavior_analysis = payload.price_behavior_analysis
    if payload.fundamentals_analysis is not None:
        report.fundamentals_analysis = payload.fundamentals_analysis
    if payload.macro_analysis is not None:
        report.macro_analysis = payload.macro_analysis
    if payload.policy_analysis is not None:
        report.policy_analysis = payload.policy_analysis
    if payload.recommendations is not None:
        report.recommendations = [
            Recommendation(
                product_code=item.product_code.upper(),
                action=item.action,
                basis=item.basis,
                risk_note=item.risk_note,
                confidence=item.confidence,
            )
            for item in payload.recommendations
        ]
    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/publish", response_model=ReportOut)
def publish(report_id: int, db: Session = Depends(get_db)) -> Report:
    report = publish_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report


@router.post("/reports/{report_id}/push", response_model=PushOut)
def push(report_id: int, db: Session = Depends(get_db)) -> PushOut:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.status == "draft":
        report = publish_report(db, report_id)
    work_status, work_message = push_report_to_wechat(db, report)
    miniapp_status, miniapp_message = push_report_to_miniapp_subscribers(db, report)
    statuses = {work_status, miniapp_status}
    status = "success" if "success" in statuses else "failed" if statuses == {"failed"} else "skipped"
    return PushOut(status=status, message=f"企业微信：{work_message}；小程序订阅消息：{miniapp_message}")


@router.post("/policy-events", response_model=PolicyEventCreateOut)
def create_event(payload: PolicyEventCreate, db: Session = Depends(get_db)) -> PolicyEventCreateOut:
    codes = [item.upper() for item in payload.product_codes if item.strip()]
    query = db.query(Product).filter(Product.is_active.is_(True))
    if codes:
        query = query.filter(Product.code.in_(codes))
    products = query.order_by(Product.display_order).all()
    if not products:
        raise HTTPException(status_code=404, detail="没有找到可写入政策事件的品种")

    events = [
        create_policy_event(
            db,
            product=product,
            title=payload.title,
            content=payload.content,
            category=payload.category,
            event_date=payload.event_date,
            impact_level=payload.impact_level,
            source=payload.source,
            url=payload.url,
        )
        for product in products
    ]
    db.commit()
    for event in events:
        db.refresh(event)

    report_id = None
    push_status = None
    message = f"已写入{len(events)}条政策/产业事件"
    if payload.push_now:
        report = generate_report(db, session_name=payload.session_name or "urgent", force=True)
        published = publish_report(db, report.id)
        report_id = published.id if published else report.id
        if published:
            work_status, work_message = push_report_to_wechat(db, published)
            miniapp_status, miniapp_message = push_report_to_miniapp_subscribers(db, published)
            push_status = "success" if "success" in {work_status, miniapp_status} else "skipped"
            message = f"{message}，已生成突发快讯并尝试推送：企业微信：{work_message}；小程序订阅消息：{miniapp_message}"

    return PolicyEventCreateOut(
        status="success",
        created=len(events),
        events=events,
        report_id=report_id,
        push_status=push_status,
        message=message,
    )


@router.get("/logs", response_model=LogsOut)
def logs(db: Session = Depends(get_db)) -> LogsOut:
    sync_logs = db.query(SyncLog).order_by(desc(SyncLog.started_at)).limit(50).all()
    push_logs = db.query(PushLog).order_by(desc(PushLog.sent_at)).limit(50).all()
    return LogsOut(sync_logs=sync_logs, push_logs=push_logs)
