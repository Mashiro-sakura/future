"""交易所前20会员持仓排名（龙虎榜）——大资金方向传感器。

定位：回答"大资金在哪个方向"，不回答"在哪个价位"（价位归成交量分布管）。
数据源=交易所官方日频（akshare get_rank_sum_daily，品种汇总行）。
指标三件套（全是结构描述）：
  1. 净多持仓 = 前20会员多头 - 空头（手）
  2. 净多变化 = 多头增减 - 空头增减（谁撤得快比谁的绝对值更有信息量）
  3. 净多分位 = 当前净多在近窗口期的位置（与 IV 分位同构，读取时现算）

DCE（PVC 等）通路断臂与波动率一致（akshare DCE 接口 BadZipFile），
V1 仅 PTA；通路修复后在 RANK_PRODUCTS 加配置即可。
"""

from __future__ import annotations

from datetime import date, timedelta

import akshare as ak
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import PositionRankDaily, Product

RANK_PRODUCTS: dict[str, str] = {
    "PTA": "TA",  # 品种汇总 symbol -> 交易所品种代码
}

RANK_LOOKBACK_DAYS = 120  # 净多分位窗口（约半年交易日）


def _fetch_rank_row(variety: str, trade_date: date) -> dict | None:
    """抓某日品种汇总行。非交易日/上游未发布返回 None（不抛异常）。"""
    try:
        df = ak.get_rank_sum_daily(start_day=trade_date.strftime("%Y%m%d"),
                                   end_day=trade_date.strftime("%Y%m%d"),
                                   vars_list=[variety])
    except Exception:
        return None
    if df is None or df.empty:
        return None
    # 品种汇总行：symbol == 品种中文名（不带合约月份），即 variety 列匹配但 symbol 无数字
    for row in df.to_dict("records"):
        symbol = str(row.get("symbol", ""))
        if symbol and not any(ch.isdigit() for ch in symbol):
            return row
    return None


def sync_position_rank_for_date(db: Session, product: Product, trade_date: date) -> PositionRankDaily | None:
    """同步某品种某交易日的前20会员排名。无配置/非交易日/无汇总行返回 None。"""
    variety = RANK_PRODUCTS.get(product.code)
    if not variety:
        return None
    row = _fetch_rank_row(variety, trade_date)
    if row is None:
        return None
    try:
        long_oi = float(row["long_open_interest_top20"])
        short_oi = float(row["short_open_interest_top20"])
    except (KeyError, TypeError, ValueError):
        return None
    record = (
        db.query(PositionRankDaily)
        .filter(PositionRankDaily.product_code == product.code, PositionRankDaily.trade_date == trade_date)
        .first()
    )
    if record is None:
        record = PositionRankDaily(product_code=product.code, trade_date=trade_date)
        db.add(record)
    record.long_top20 = long_oi
    record.short_top20 = short_oi
    record.long_chg_top20 = _to_float(row.get("long_open_interest_chg_top20"))
    record.short_chg_top20 = _to_float(row.get("short_open_interest_chg_top20"))
    record.net_long = long_oi - short_oi
    record.source = "akshare:exchange-rank-top20"
    return record


def _to_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def sync_position_rank_daily(db: Session, days: int = 5) -> str:
    """近 days 个自然日逐日同步（非交易日自动跳过）。供 sync_market_data 调用。"""
    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    rank_products = [p for p in products if p.code in RANK_PRODUCTS]
    if not rank_products:
        return "持仓排名: 无品种配置"
    written = 0
    today = date.today()
    for offset in range(days):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        for product in rank_products:
            if sync_position_rank_for_date(db, product, day) is not None:
                written += 1
    return f"持仓排名: 写入/更新{written}条"


def _zone(percentile: float) -> str:
    if percentile <= 20:
        return "低位区"
    if percentile >= 80:
        return "高位区"
    return "中位区"


def position_rank_snapshot(db: Session, code: str, window: int = RANK_LOOKBACK_DAYS) -> dict | None:
    """最新排名快照 + 净多分位（读取时现算，与 IV/基差分位同构）。"""
    code = code.upper()
    if code not in RANK_PRODUCTS:
        return None
    rows = (
        db.query(PositionRankDaily)
        .filter(PositionRankDaily.product_code == code)
        .order_by(desc(PositionRankDaily.trade_date))
        .limit(window)
        .all()
    )
    if not rows:
        return None
    latest = rows[0]
    nets = [r.net_long for r in rows if r.net_long is not None]
    percentile = None
    zone = None
    if nets:
        below = sum(1 for v in nets if v <= latest.net_long)
        percentile = round(below / len(nets) * 100, 1)
        zone = _zone(percentile)
    long_chg = latest.long_chg_top20 or 0
    short_chg = latest.short_chg_top20 or 0
    net_chg = long_chg - short_chg
    total = latest.long_top20 + latest.short_top20
    return {
        "code": code,
        "trade_date": latest.trade_date,
        "long_top20": latest.long_top20,
        "long_chg_top20": latest.long_chg_top20,
        "short_top20": latest.short_top20,
        "short_chg_top20": latest.short_chg_top20,
        "net_long": latest.net_long,
        "net_chg": net_chg,
        "long_pct": round(latest.long_top20 / total * 100, 1) if total > 0 else None,
        "net_percentile": percentile,
        "zone": zone,
        "sample_days": len(nets),
        "window": window,
        "source": latest.source,
    }
