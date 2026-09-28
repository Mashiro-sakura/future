"""分席位持仓（L2 席位白名单）——聪明钱聚集效应传感器。

定位：L1（position_rank 前20汇总）回答"大资金整体在哪边"，
L2 回答"**哪些具体席位**在动"。白名单来源=老板提供的 2026 年 1-8 月
各席位分品种盈亏榜（乾坤 TA +6.17 亿/东证胜率 84% 等实证）。

数据源（akshare，均交易所官方日频前20榜）：
  - CZCE get_rank_table_czce：dict[品种/合约] → 品种汇总键直取（如 'PTA'）
  - SHFE get_shfe_rank_table：dict[合约] → 跨合约按席位聚合（近似品种级）
  - DCE futures_dce_position_rank：BadZipFile（瑞数），不可用，DCE 品种不配置

口径三条（写死在文案里）：
  1. 席位=期货公司，盈亏/持仓是其全部客户的合计，非自营盘——跟踪的是聪明钱聚集
  2. SHFE 聚合=各合约前20榜求和，席位在某合约掉出前20则该部分不计（近似值）
  3. 白名单席位跌出前20=本身是信号（缩仓/移仓），快照层标 missing 而非报错
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import akshare as ak
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Product, SeatPositionDaily

# ---------------------------------------------------------------------------
# 白名单配置（来源：2026 年 1-8 月席位分品种盈亏实证，老板拍板表）
# follow=盈利实证席位（跟），counter=亏损实证席位（对手盘信号）
# 全品种通用聪明钱：永安/国泰君安/东证（总榜前三，东证胜率 84%）
# ---------------------------------------------------------------------------
SEAT_PRODUCTS: dict[str, dict] = {
    "PTA": {
        "exchange": "CZCE",
        "variety": "PTA",
        "follow": ["乾坤", "永安", "国泰君安", "东证", "高盛"],
        "counter": ["东吴", "兴证"],
        "source": "czce-rank-variety",
    },
    "PX": {
        "exchange": "CZCE",
        "variety": "PX",
        "follow": ["永安", "国泰君安", "东证"],
        "counter": [],
        "source": "czce-rank-variety",
    },
    "CU": {
        "exchange": "SHFE",
        "variety": "CU",
        "follow": ["国信", "国泰君安", "东证", "永安"],
        "counter": ["云晨"],
        "source": "shfe-rank-aggregated",
    },
    "PB": {
        "exchange": "SHFE",
        "variety": "PB",
        "follow": ["国泰君安", "东证", "永安"],
        "counter": [],
        "source": "shfe-rank-aggregated",
    },
    # DCE 品种（PVC/LLDPE/PP/P/PL）：futures_dce_position_rank BadZipFile 不可用，
    # 通路修复后按同样结构补配置即可。
}

_SUFFIX_RE = re.compile(r"（[^（）]*）$")


def normalize_party(name: str) -> str:
    """归一化席位名：去尾部（代客）/（自营）/（资管）括号后缀。

    国泰君安（代客）+国泰君安（自营）→ 国泰君安（聚合时求和合并）。
    """
    return _SUFFIX_RE.sub("", (name or "").strip())


def _to_float(v) -> float | None:
    try:
        return float(str(v).replace(",", "")) if v is not None else None
    except (TypeError, ValueError):
        return None


def _aggregate_rows(rows: list[dict]) -> dict[str, dict]:
    """把榜单行聚合成 {席位: {long_oi, long_chg, short_oi, short_chg}}。

    同一席位多头榜/空头榜/代客自营分别出现 → 全部求和。
    """
    agg: dict[str, dict] = {}
    for row in rows:
        name = normalize_party(str(row.get("long_party_name") or ""))
        if name:
            slot = agg.setdefault(name, {"long_oi": 0.0, "long_chg": 0.0, "short_oi": 0.0, "short_chg": 0.0})
            slot["long_oi"] += _to_float(row.get("long_open_interest")) or 0.0
            slot["long_chg"] += _to_float(row.get("long_open_interest_chg")) or 0.0
        name = normalize_party(str(row.get("short_party_name") or ""))
        if name:
            slot = agg.setdefault(name, {"long_oi": 0.0, "long_chg": 0.0, "short_oi": 0.0, "short_chg": 0.0})
            slot["short_oi"] += _to_float(row.get("short_open_interest")) or 0.0
            slot["short_chg"] += _to_float(row.get("short_open_interest_chg")) or 0.0
    return agg


def _fetch_czce_seats(variety: str, trade_date: date) -> dict[str, dict] | None:
    """郑商所品种汇总榜（dict 的品种级键，如 'PTA'）。"""
    table = ak.get_rank_table_czce(date=trade_date.strftime("%Y%m%d"))
    if not isinstance(table, dict) or variety not in table:
        return None
    df = table[variety]
    if df is None or df.empty:
        return None
    return _aggregate_rows(df.to_dict("records"))


def _fetch_shfe_seats(variety: str, trade_date: date) -> dict[str, dict] | None:
    """上期所：合约级榜跨合约按席位求和（近似品种级）。"""
    table = ak.get_shfe_rank_table(date=trade_date.strftime("%Y%m%d"), vars_list=[variety])
    if not isinstance(table, dict) or not table:
        return None
    rows: list[dict] = []
    for df in table.values():
        if df is None or df.empty:
            continue
        rows.extend(df.to_dict("records"))
    if not rows:
        return None
    return _aggregate_rows(rows)


def sync_seat_rank_for_date(db: Session, product: Product, trade_date: date) -> int:
    """同步某品种某交易日的全席位榜。返回写入条数；无配置/非交易日返回 0。"""
    conf = SEAT_PRODUCTS.get(product.code)
    if not conf:
        return 0
    try:
        if conf["exchange"] == "CZCE":
            seats = _fetch_czce_seats(conf["variety"], trade_date)
        else:
            seats = _fetch_shfe_seats(conf["variety"], trade_date)
    except Exception:
        return 0
    if not seats:
        return 0
    written = 0
    for name, vals in seats.items():
        record = (
            db.query(SeatPositionDaily)
            .filter(
                SeatPositionDaily.product_code == product.code,
                SeatPositionDaily.trade_date == trade_date,
                SeatPositionDaily.party_name == name,
            )
            .first()
        )
        if record is None:
            record = SeatPositionDaily(product_code=product.code, trade_date=trade_date, party_name=name)
            db.add(record)
        record.long_oi = vals["long_oi"] or None
        record.long_chg = vals["long_chg"] or None
        record.short_oi = vals["short_oi"] or None
        record.short_chg = vals["short_chg"] or None
        record.source = conf["source"]
        written += 1
    return written


def sync_seat_rank_daily(db: Session, days: int = 5) -> str:
    """近 days 个自然日逐日同步（非交易日自动跳过）。供 sync_market_data 调用。"""
    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    seat_products = [p for p in products if p.code in SEAT_PRODUCTS]
    if not seat_products:
        return "席位持仓: 无品种配置"
    written = 0
    today = date.today()
    for offset in range(days):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        for product in seat_products:
            written += sync_seat_rank_for_date(db, product, day)
    return f"席位持仓: 写入/更新{written}条"


def _match_party(stored_names: list[str], key: str) -> str | None:
    """白名单关键字 → 库内全名匹配（前缀双向）。

    库内存官方全名（永安期货/东证期货/国泰君安），白名单配短名（永安/东证）。
    取前缀匹配最长的一条（防"中信"误配"中信建投"/"中信期货"时取更精确的）。
    """
    key = key.strip()
    if not key:
        return None
    hits = [n for n in stored_names if n.startswith(key) or key.startswith(n)]
    if not hits:
        return None
    return max(hits, key=len)


def seat_rank_snapshot(db: Session, code: str) -> dict | None:
    """白名单席位最新快照：每席最新持仓+净头寸+较前一日净变化。

    白名单席位不在最新榜（跌出前20）→ 该席 missing=True（缩仓/移仓信号），
    同时回看上一条历史记录给出参考值。
    """
    code = code.upper()
    conf = SEAT_PRODUCTS.get(code)
    if not conf:
        return None
    follow = conf["follow"]
    counter = conf["counter"]
    whitelist = follow + counter
    latest_date = (
        db.query(SeatPositionDaily.trade_date)
        .filter(SeatPositionDaily.product_code == code)
        .order_by(desc(SeatPositionDaily.trade_date))
        .limit(1)
        .scalar()
    )
    if latest_date is None:
        return None
    latest_rows = {
        r.party_name: r
        for r in db.query(SeatPositionDaily)
        .filter(SeatPositionDaily.product_code == code, SeatPositionDaily.trade_date == latest_date)
        .all()
    }
    prev_date = (
        db.query(SeatPositionDaily.trade_date)
        .filter(SeatPositionDaily.product_code == code, SeatPositionDaily.trade_date < latest_date)
        .order_by(desc(SeatPositionDaily.trade_date))
        .limit(1)
        .scalar()
    )
    prev_rows = {}
    if prev_date is not None:
        prev_rows = {
            r.party_name: r
            for r in db.query(SeatPositionDaily)
            .filter(SeatPositionDaily.product_code == code, SeatPositionDaily.trade_date == prev_date)
            .all()
        }
    seats_out = []
    stored_names = list(latest_rows.keys())
    for name in whitelist:
        role = "follow" if name in follow else "counter"
        matched = _match_party(stored_names, name)
        row = latest_rows.get(matched) if matched else None
        prev = prev_rows.get(matched) if matched else None
        if row is None:
            seats_out.append(
                {
                    "party": name,
                    "role": role,
                    "missing": True,
                    "long_oi": None,
                    "short_oi": None,
                    "net": None,
                    "net_chg_1d": None,
                    "note": "跌出前20" + (f"（前值净{'多' if (prev.long_oi or 0) - (prev.short_oi or 0) >= 0 else '空'}）" if prev else ""),
                }
            )
            continue
        net = (row.long_oi or 0) - (row.short_oi or 0)
        prev_net = (prev.long_oi or 0) - (prev.short_oi or 0) if prev else None
        seats_out.append(
            {
                "party": name,
                "role": role,
                "missing": False,
                "long_oi": row.long_oi,
                "long_chg": row.long_chg,
                "short_oi": row.short_oi,
                "short_chg": row.short_chg,
                "net": net,
                "net_chg_1d": net - prev_net if prev_net is not None else None,
            }
        )
    return {
        "code": code,
        "trade_date": latest_date,
        "prev_date": prev_date,
        "exchange": conf["exchange"],
        "seats": seats_out,
        "follow_count": len(follow),
        "counter_count": len(counter),
        "source": conf["source"],
    }
