from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import Product, Report, WechatMiniappSubscriber
from app.schemas import (
    BasisDetailOut,
    BasisOverviewItem,
    MiniappSubscribeConfigOut,
    MiniappSubscriptionIn,
    MiniappSubscriptionOut,
    OverviewOut,
    ProductOut,
    RealtimeQuoteOut,
    ReportOut,
    TrendPoint,
    VolatilityOut,
)
from app.services.analytics import overview_products, trend_points
from app.services.basis import BASIS_LOOKBACK_DAYS, basis_overview, basis_series, basis_snapshot
from app.services.volatility import volatility_snapshot
from app.services.reports import ensure_report_analysis, latest_public_report
from app.services.wechat_miniapp import WechatMiniappApiError, exchange_code_for_openid, is_wechat_miniapp_subscription_configured

router = APIRouter(prefix="/api/public", tags=["public"])

MIN_WINDOW = 10


@router.get("/wechat/subscribe-config", response_model=MiniappSubscribeConfigOut)
def miniapp_subscribe_config() -> MiniappSubscribeConfigOut:
    settings = get_settings()
    enabled = is_wechat_miniapp_subscription_configured()
    message = "订阅消息可用" if enabled else "后台尚未配置微信小程序订阅消息凭据"
    return MiniappSubscribeConfigOut(
        enabled=enabled,
        template_id=settings.wechat_subscribe_template_id if enabled else None,
        message=message,
    )


@router.post("/wechat/subscriptions", response_model=MiniappSubscriptionOut)
def create_miniapp_subscription(payload: MiniappSubscriptionIn, db: Session = Depends(get_db)) -> MiniappSubscriptionOut:
    settings = get_settings()
    if not is_wechat_miniapp_subscription_configured():
        raise HTTPException(status_code=503, detail="后台尚未配置微信小程序订阅消息凭据")
    if payload.template_id != settings.wechat_subscribe_template_id:
        raise HTTPException(status_code=400, detail="订阅模板与当前配置不一致，请刷新后重试")
    try:
        openid = exchange_code_for_openid(payload.code)
    except WechatMiniappApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"微信登录凭证校验失败：{exc}") from exc

    subscriber = db.query(WechatMiniappSubscriber).filter(WechatMiniappSubscriber.openid == openid).first()
    if subscriber is None:
        subscriber = WechatMiniappSubscriber(
            openid=openid,
            template_id=payload.template_id,
            subscription_count=1,
            is_active=True,
        )
        db.add(subscriber)
    else:
        subscriber.template_id = payload.template_id
        subscriber.subscription_count += 1
        subscriber.is_active = True
        subscriber.last_subscribed_at = datetime.utcnow()
    db.commit()
    db.refresh(subscriber)
    return MiniappSubscriptionOut(
        status="success",
        message="已订阅下一次日报提醒",
        subscription_count=subscriber.subscription_count,
    )


@router.get("/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_db)) -> OverviewOut:
    report = latest_public_report(db)
    return OverviewOut(latest_report=report, products=overview_products(db, report))


def _is_trading_time(now: datetime) -> bool:
    """粗粒度交易时段：工作日 09:00-10:15 / 10:30-11:30 / 13:30-15:00 / 21:00-23:30。

    档1 不追求交易所级精确（节假日前夜夜盘暂停、部分品种 01:00/02:30 收盘等不展开），
    前端据此决定是否启动轮询，宁可在边界时刻多显示一会"已收盘"。
    """
    if now.weekday() >= 5:
        return False
    hm = now.hour * 100 + now.minute
    return (900 <= hm <= 1015) or (1030 <= hm <= 1130) or (1330 <= hm <= 1500) or (2100 <= hm <= 2330)


@router.get("/realtime", response_model=list[RealtimeQuoteOut])
def realtime_quotes(db: Session = Depends(get_db)) -> list[RealtimeQuoteOut]:
    """盘中准实时快照：新浪透传（60s 缓存，不写库），涨跌基准=库内最近收盘价。"""
    from app.models import FuturesPrice
    from app.services.data_fetcher import fetch_realtime_main_quotes

    products = db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.display_order).all()
    quotes = fetch_realtime_main_quotes(products)
    trading = _is_trading_time(datetime.now())
    now = datetime.now()
    out: list[RealtimeQuoteOut] = []
    for product in products:
        row = quotes.get(product.code)
        prev_close: float | None = None
        if row is not None:
            prev = (
                db.query(FuturesPrice)
                .filter(FuturesPrice.product_code == product.code, FuturesPrice.trade_date < row.trade_date)
                .order_by(desc(FuturesPrice.trade_date))
                .first()
            )
            prev_close = prev.close_price if prev else None
        change_pct = (
            round((row.close_price - prev_close) / prev_close * 100, 2)
            if row is not None and prev_close not in (None, 0)
            else None
        )
        out.append(
            RealtimeQuoteOut(
                code=product.code,
                contract_code=row.contract_code if row else None,
                price=row.close_price if row else None,
                prev_close=prev_close,
                change_pct=change_pct,
                volume=row.volume if row else None,
                open_interest=row.open_interest if row else None,
                trade_date=row.trade_date if row else None,
                trading_now=trading,
                server_time=now,
            )
        )
    return out


@router.get("/products", response_model=list[ProductOut])
def products(db: Session = Depends(get_db)) -> list[Product]:
    return db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.display_order).all()


@router.get("/products/{code}/trend", response_model=list[TrendPoint])
def product_trend(code: str, days: int = 60, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    product = db.query(Product).filter(Product.code == code.upper(), Product.is_active.is_(True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="品种不存在")
    return trend_points(db, product.code, days=days)


@router.get("/basis", response_model=list[BasisOverviewItem])
def basis_list(window: int = BASIS_LOOKBACK_DAYS, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    safe_window = max(MIN_WINDOW, min(window, BASIS_LOOKBACK_DAYS))
    return basis_overview(db, window=safe_window)


@router.get("/basis/{code}", response_model=BasisDetailOut)
def basis_detail(code: str, days: int = 120, db: Session = Depends(get_db)) -> dict[str, object]:
    product = db.query(Product).filter(Product.code == code.upper(), Product.is_active.is_(True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="品种不存在")
    if not product.futures_symbol:
        raise HTTPException(status_code=400, detail="该品种为纯现货跟踪，无期货基差")
    safe_days = max(MIN_WINDOW, min(days, BASIS_LOOKBACK_DAYS))
    snapshot = basis_snapshot(db, product.code, window=BASIS_LOOKBACK_DAYS)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="该品种暂无期货或现货数据，无法计算基差")
    history = basis_series(db, product.code, days=safe_days)
    snapshot["name"] = product.name
    return {"snapshot": snapshot, "history": history}


@router.get("/volatility/{code}", response_model=VolatilityOut)
def volatility_detail(code: str, db: Session = Depends(get_db)) -> dict[str, object]:
    snapshot = volatility_snapshot(db, code)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="该品种暂无期权波动率数据")
    return snapshot


@router.get("/reports/latest", response_model=ReportOut)
def latest_report(db: Session = Depends(get_db)) -> Report:
    report = latest_public_report(db)
    if not report:
        raise HTTPException(status_code=404, detail="暂无已发布报告")
    return report


@router.get("/reports", response_model=list[ReportOut])
def report_list(limit: int = 20, db: Session = Depends(get_db)) -> list[Report]:
    safe_limit = max(1, min(limit, 100))
    reports = (
        db.query(Report)
        .filter(Report.status.in_(["published", "pushed"]))
        .order_by(desc(Report.published_at), desc(Report.generated_at))
        .limit(safe_limit)
        .all()
    )
    return [ensure_report_analysis(db, report) for report in reports if report]


@router.get("/reports/{report_id}", response_model=ReportOut)
def report_detail(report_id: int, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if not report or report.status not in {"published", "pushed"}:
        raise HTTPException(status_code=404, detail="报告不存在或未发布")
    return ensure_report_analysis(db, report)
