"""基差计算服务（P0 · 期现视角）。

基差 = 现货基准价（华东） − 期货主力收盘价。
正值 = 现货升水；负值 = 现货贴水。

数字纪律：
- 分位按实际可得样本计算（window 只是上限），返回 sample_days 如实告知样本量；
  样本不足 MIN_SAMPLE_DAYS 时不给分位，给 null，前端显示"样本不足"。
- 现货与期货最新日期不对齐时，快照取两边都有数据的最新一日，
  并分别返回两侧日期 + data_stale 标记（相差 >7 天视为脏数据）。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import FuturesPrice, Product, SpotPrice
from app.services.analytics import BENCHMARK_SPOT_REGION

BASIS_LOOKBACK_DAYS = 250
MIN_SAMPLE_DAYS = 10
STALE_DATE_GAP_DAYS = 7
FLAT_BASIS_THRESHOLD = 10.0


def _days_since(trade_date: date) -> int:
    if not trade_date:
        return 999
    return (datetime.now().date() - trade_date).days


def _basis_label(value: float) -> str:
    if value > FLAT_BASIS_THRESHOLD:
        return "升水"
    if value < -FLAT_BASIS_THRESHOLD:
        return "贴水"
    return "平水"


def _zone(percentile: float) -> str:
    if percentile <= 20:
        return "低位区"
    if percentile >= 80:
        return "高位区"
    return "中位区"


def basis_series(db: Session, code: str, days: int = BASIS_LOOKBACK_DAYS) -> list[dict[str, object]]:
    """按交易日对齐期货收盘与华东现货价，输出基差序列（升序）。"""
    futures_rows = (
        db.query(FuturesPrice)
        .filter(FuturesPrice.product_code == code)
        .order_by(desc(FuturesPrice.trade_date))
        .limit(days)
        .all()
    )
    spot_rows = (
        db.query(SpotPrice)
        .filter(SpotPrice.product_code == code, SpotPrice.region == BENCHMARK_SPOT_REGION)
        .order_by(desc(SpotPrice.trade_date))
        .limit(days)
        .all()
    )
    by_date: dict[date, dict[str, object]] = {}
    for row in futures_rows:
        by_date.setdefault(row.trade_date, {"trade_date": row.trade_date})
        by_date[row.trade_date].update(
            {
                "futures_contract": row.contract_code or None,
                "futures_close": row.close_price,
            }
        )
    for row in spot_rows:
        by_date.setdefault(row.trade_date, {"trade_date": row.trade_date})
        by_date[row.trade_date]["spot_price"] = row.price
    points: list[dict[str, object]] = []
    for key in sorted(by_date.keys()):
        item = by_date[key]
        futures_close = item.get("futures_close")
        spot_price = item.get("spot_price")
        if futures_close is not None and spot_price is not None:
            item["basis_value"] = round(spot_price - futures_close, 2)
        else:
            item["basis_value"] = None
        points.append(item)
    return points


def basis_snapshot(db: Session, code: str, window: int = BASIS_LOOKBACK_DAYS) -> dict[str, object] | None:
    """单品种基差快照：最新基差、窗口分位、区间归属、样本量。"""
    series = basis_series(db, code, days=window)
    if not series:
        return None
    latest_row = next((item for item in reversed(series) if item.get("basis_value") is not None), None)
    if latest_row is None:
        return None

    values = [item["basis_value"] for item in series if item.get("basis_value") is not None]
    sample_days = len(values)
    current = latest_row["basis_value"]

    percentile: float | None = None
    zone: str | None = None
    if sample_days >= MIN_SAMPLE_DAYS:
        below = sum(1 for value in values if value <= current)
        percentile = round(below / sample_days * 100, 1)
        zone = _zone(percentile)

    return {
        "code": code,
        "basis_value": current,
        "basis_label": _basis_label(current),
        "futures_close": latest_row.get("futures_close"),
        "spot_price": latest_row.get("spot_price"),
        "futures_contract": latest_row.get("futures_contract"),
        "trade_date": latest_row["trade_date"],
        "days_since_last": _days_since(latest_row["trade_date"]),
        "data_stale": _days_since(latest_row["trade_date"]) > STALE_DATE_GAP_DAYS,
        "percentile": percentile,
        "zone": zone,
        "sample_days": sample_days,
        "window": min(window, BASIS_LOOKBACK_DAYS),
    }


def basis_overview(db: Session, window: int = BASIS_LOOKBACK_DAYS) -> list[dict[str, object]]:
    """全部有期货合约的活跃品种基差快照（辛醇等纯现货品种跳过）。"""
    products = (
        db.query(Product)
        .filter(Product.is_active.is_(True), Product.futures_symbol != "")
        .order_by(Product.display_order)
        .all()
    )
    rows: list[dict[str, object]] = []
    for product in products:
        snapshot = basis_snapshot(db, product.code, window=window)
        if snapshot is None:
            continue
        snapshot["name"] = product.name
        rows.append(snapshot)
    return rows
