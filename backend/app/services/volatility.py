"""期权波动率传感器（V1: PTA/郑商所）。

定位：用期权数据辅助期货分析，不是期权交易工具。
三个结构指标：
  1. ATM IV（平值隐含波动率）——直接取郑商所官方发布值，零自算
  2. HV20（20 日历史波动率）——自家期货日线对数收益 std × √252，纯代码
  3. IV 分位 + IV-HV 利差——endpoint 读取时基于近一年历史现算（与 basis 分位同构）

数据源纪律：郑商所日行情（akshare option_hist_czce）每日一次，日频足够；
盘中 IV 不做（同档3战略：速度是同花顺的战场，结构才是差异化）。
PVC（大商所）通路未通，V1 仅 PTA，新品种接入只需在 OPTION_PRODUCTS 加配置。
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

import akshare as ak
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import FuturesPrice, Product, VolatilityDaily

# V1 仅 PTA。exchange 目前只实现 CZCE；DCE（PVC）通路待修后在此加配置即可。
OPTION_PRODUCTS: dict[str, dict[str, str]] = {
    "PTA": {"exchange": "CZCE", "option_symbol": "PTA期权"},
}

VOLATILITY_LOOKBACK_DAYS = 252  # IV 分位窗口（约一年交易日）
HV_WINDOW = 20  # 历史波动率窗口

# 郑商所期权合约代码：TA611C4750 → 标的月 TA611 + C/P + 行权价 4750
_CONTRACT_RE = re.compile(r"^([A-Za-z]+\d{3,4})([CP])(\d+(?:\.\d+)?)$")


def parse_option_contract(contract_code: str) -> tuple[str, str, float] | None:
    """解析商品期权合约代码 → (标的月份, C/P, 行权价)。解析失败返回 None。"""
    m = _CONTRACT_RE.match((contract_code or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2), float(m.group(3))


def _fetch_option_daily_czce(option_symbol: str, trade_date: date) -> list[dict]:
    """抓郑商所期权日行情。非交易日/上游未发布返回空列表（不抛异常）。"""
    try:
        df = ak.option_hist_czce(symbol=option_symbol, trade_date=trade_date.strftime("%Y%m%d"))
    except Exception:
        return []
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def extract_atm_iv(rows: list[dict], futures_ref: float) -> dict | None:
    """从一日期权全量行情中提取 ATM IV。

    标的选择：期权持仓量合计最大的月份（= 市场公认主力月，无需猜期货主力换月）。
    ATM 选择：行权价距 futures_ref 最近的档位，call/put IV 取均值。
    IV 口径：郑商所官方发布的隐含波动率（百分比），成交量/持仓量均为 0 的深度
    虚实盘档位 IV 失真，要求候选档位 call 或 put 至少一边有持仓。
    """
    by_month: dict[str, dict[str, dict[float, dict[str, float]]]] = {}
    month_oi: dict[str, float] = {}
    for row in rows:
        parsed = parse_option_contract(str(row.get("合约代码", "")))
        if not parsed:
            continue
        month, cp, strike = parsed
        iv = row.get("隐含波动率")
        oi = row.get("持仓量") or 0
        try:
            iv = float(iv) if iv is not None else None
            oi = float(oi)
        except (TypeError, ValueError):
            continue
        month_oi[month] = month_oi.get(month, 0.0) + oi
        if iv is None or iv <= 0:
            continue
        month_book = by_month.setdefault(month, {"C": {}, "P": {}})
        month_book[cp][strike] = iv
    if not month_oi:
        return None
    main_month = max(month_oi, key=lambda m: month_oi[m])
    book = by_month.get(main_month)
    if not book:
        return None
    # 候选档位 = call/put 都有 IV 的行权价，取距期货价最近者
    common = set(book["C"]) & set(book["P"])
    if not common:
        return None
    atm_strike = min(common, key=lambda s: abs(s - futures_ref))
    call_iv = book["C"][atm_strike]
    put_iv = book["P"][atm_strike]
    return {
        "underlying_month": main_month,
        "atm_strike": atm_strike,
        "call_iv": round(call_iv, 2),
        "put_iv": round(put_iv, 2),
        "atm_iv": round((call_iv + put_iv) / 2, 2),
    }


def compute_hv(closes: list[float], window: int = HV_WINDOW) -> float | None:
    """20 日历史波动率（年化，百分比）。需要 window+1 个收盘价，不足返回 None。"""
    prices = [c for c in closes if c and c > 0]
    if len(prices) < window + 1:
        return None
    rets = [math.log(prices[i] / prices[i - 1]) for i in range(len(prices) - window, len(prices))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(252) * 100, 2)


def _futures_closes_before(db: Session, product_code: str, trade_date: date, limit: int = 30) -> list[float]:
    rows = (
        db.query(FuturesPrice.close_price)
        .filter(FuturesPrice.product_code == product_code, FuturesPrice.trade_date <= trade_date)
        .order_by(desc(FuturesPrice.trade_date))
        .limit(limit)
        .all()
    )
    return [r[0] for r in reversed(rows)]  # 时间升序


def _futures_ref_price(db: Session, product_code: str, trade_date: date) -> float | None:
    """期货参考价：当日主力连续收盘价，当日缺则取之前最近一日。"""
    row = (
        db.query(FuturesPrice.close_price)
        .filter(FuturesPrice.product_code == product_code, FuturesPrice.trade_date <= trade_date)
        .order_by(desc(FuturesPrice.trade_date))
        .first()
    )
    return row[0] if row else None


def sync_volatility_for_date(db: Session, product: Product, trade_date: date) -> VolatilityDaily | None:
    """同步某品种某交易日的波动率快照。无期权配置/非交易日/数据缺失返回 None。"""
    cfg = OPTION_PRODUCTS.get(product.code)
    if not cfg:
        return None
    if cfg["exchange"] != "CZCE":
        return None  # V1 仅实现郑商所
    rows = _fetch_option_daily_czce(cfg["option_symbol"], trade_date)
    if not rows:
        return None
    futures_ref = _futures_ref_price(db, product.code, trade_date)
    if futures_ref is None:
        return None
    atm = extract_atm_iv(rows, futures_ref)
    if atm is None:
        return None
    closes = _futures_closes_before(db, product.code, trade_date)
    hv20 = compute_hv(closes)
    record = (
        db.query(VolatilityDaily)
        .filter(VolatilityDaily.product_code == product.code, VolatilityDaily.trade_date == trade_date)
        .first()
    )
    if record is None:
        record = VolatilityDaily(product_code=product.code, trade_date=trade_date)
        db.add(record)
    record.underlying_month = atm["underlying_month"]
    record.futures_ref = futures_ref
    record.atm_strike = atm["atm_strike"]
    record.atm_iv = atm["atm_iv"]
    record.call_iv = atm["call_iv"]
    record.put_iv = atm["put_iv"]
    record.hv20 = hv20
    record.source = "akshare:czce-option-daily"
    return record


def sync_volatility_daily(db: Session, days: int = 5) -> str:
    """近 days 个自然日逐日同步全部期权品种（非交易日自动跳过）。供 sync_market_data 调用。"""
    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    option_products = [p for p in products if p.code in OPTION_PRODUCTS]
    if not option_products:
        return "波动率: 无期权品种配置"
    written = 0
    today = date.today()
    for offset in range(days):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        for product in option_products:
            if sync_volatility_for_date(db, product, day) is not None:
                written += 1
    return f"波动率: 写入/更新{written}条"


def _zone(percentile: float) -> str:
    if percentile <= 20:
        return "低位区"
    if percentile >= 80:
        return "高位区"
    return "中位区"


def volatility_snapshot(db: Session, code: str, window: int = VOLATILITY_LOOKBACK_DAYS) -> dict | None:
    """读取最新波动率快照 + IV 分位（与 basis_snapshot 同构，分位读取时现算）。"""
    code = code.upper()
    if code not in OPTION_PRODUCTS:
        return None
    rows = (
        db.query(VolatilityDaily)
        .filter(VolatilityDaily.product_code == code)
        .order_by(desc(VolatilityDaily.trade_date))
        .limit(window)
        .all()
    )
    if not rows:
        return None
    latest = rows[0]
    ivs = [r.atm_iv for r in rows if r.atm_iv is not None]
    percentile = None
    zone = None
    if ivs:
        below = sum(1 for v in ivs if v <= latest.atm_iv)
        percentile = round(below / len(ivs) * 100, 1)
        zone = _zone(percentile)
    iv_hv_spread = round(latest.atm_iv - latest.hv20, 2) if latest.hv20 is not None else None
    return {
        "code": code,
        "trade_date": latest.trade_date,
        "underlying_month": latest.underlying_month,
        "futures_ref": latest.futures_ref,
        "atm_strike": latest.atm_strike,
        "atm_iv": latest.atm_iv,
        "call_iv": latest.call_iv,
        "put_iv": latest.put_iv,
        "hv20": latest.hv20,
        "iv_hv_spread": iv_hv_spread,
        "iv_percentile": percentile,
        "zone": zone,
        "sample_days": len(ivs),
        "window": window,
        "source": latest.source,
    }
