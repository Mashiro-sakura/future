"""历史行情回填脚本——绕过 sync 链路，直接用真实数据源回填期货/现货日线。

为什么单独写：
- sync 链路面向"日常增量"，长历史回填应该一次性、可验证、先入副本库再动正式库。
- 期货走 akshare 主力连续日线（futures_main_sina），换月自动正确
  （历史每天的主力是当时的真实主力，不拿当前合约硬套）。
- 现货走 ak.futures_spot_price(yyyymmdd) 逐交易日拉取（一次返回全品种），
  华东记真实来源，华南/西南按 REGIONAL_SPOT_OFFSETS 估算并打 regional-estimate 标。

用法：
  python scripts/backfill_history.py [--days 140] [--db PATH] [--futures-only|--spot-only]
默认 db=./future_analysis.db。先 --db .ref/backfill_test.db 验证再动正式库。

注意（踩过的坑）：app.database 模块导入末尾会 configure_database() 一次，
`from app.database import SessionLocal` 会在导入时绑定旧引擎——之后即使重新
configure，脚本仍写旧库。必须 import 模块、configure 之后再从模块取 SessionLocal。
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import reset_settings_cache  # noqa: E402
import app.database as database  # noqa: E402  （必须模块级 import，见 docstring）
from app.models import FuturesPrice, Product, SpotPrice  # noqa: E402
from app.services.data_fetcher import (  # noqa: E402
    AKSHARE_SPOT_SYMBOL_MAP,
    REGIONAL_SPOT_OFFSETS,
    SPOT_REGIONS,
)

FUTURES_SOURCE_TAG = "akshare:sina-main-contract"
SPOT_SOURCE_TAG = "akshare:futures_spot_price"


def parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
        except ValueError:
            continue
    return None


def recent_weekdays(count: int, today: date | None = None) -> list[date]:
    """最近 count 个工作日（周末跳过；节假日数据方返回空自然过滤）。返回升序。"""
    today = today or date.today()
    found: list[date] = []
    cursor = today
    while len(found) < count:
        if cursor.weekday() < 5:
            found.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(found)


def backfill_futures_product(db, product: Product, days: int) -> tuple[int, str, str]:
    """单品种期货回填：主力连续日线最近 days 条 upsert，返回(写入数, 首末日期)。"""
    import akshare as ak

    symbol = product.futures_symbol  # 例 TA0 / V0 / CU0
    df = ak.futures_main_sina(symbol=symbol)
    if df is None or df.empty:
        return 0, "-", "-"
    rows = df.tail(days)
    written = 0
    first_date = last_date = None
    for record in rows.to_dict("records"):
        trade_date = parse_date(record.get("日期"))
        close_price = record.get("收盘价")
        if not trade_date or close_price is None:
            continue
        existing = (
            db.query(FuturesPrice)
            .filter(FuturesPrice.product_code == product.code, FuturesPrice.trade_date == trade_date)
            .first()
        )
        values = {
            "open_price": record.get("开盘价"),
            "high_price": record.get("最高价"),
            "low_price": record.get("最低价"),
            "close_price": close_price,
            "settlement_price": record.get("动态结算价") or None,
            "contract_code": product.futures_symbol,  # 主力连续，如实标注非具体合约
            "volume": record.get("成交量"),
            "open_interest": record.get("持仓量"),
            "source": FUTURES_SOURCE_TAG,
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            db.add(FuturesPrice(product_code=product.code, trade_date=trade_date, **values))
        written += 1
        if first_date is None:
            first_date = trade_date
        last_date = trade_date
    return written, str(first_date), str(last_date)


def backfill_spot(db, products: list[Product], days: int) -> int:
    """现货回填：逐交易日拉 futures_spot_price（全品种一次返回），写入数。"""
    import akshare as ak

    # ak_symbol -> product
    target: dict[str, Product] = {}
    for product in products:
        ak_symbol = AKSHARE_SPOT_SYMBOL_MAP.get((product.spot_symbol or "").strip())
        if ak_symbol:
            target[ak_symbol] = product
    if not target:
        return 0

    written = 0
    for trade_day in recent_weekdays(days):
        try:
            df = ak.futures_spot_price(trade_day.strftime("%Y%m%d"))
        except Exception:
            continue
        if df is None or getattr(df, "empty", True):
            continue
        for record in df.to_dict("records"):
            symbol = str(record.get("symbol") or "").strip().upper()
            product = target.get(symbol)
            if product is None:
                continue
            trade_date = parse_date(record.get("date")) or trade_day
            price = record.get("spot_price")
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            for region in SPOT_REGIONS:
                existing = (
                    db.query(SpotPrice)
                    .filter(
                        SpotPrice.product_code == product.code,
                        SpotPrice.trade_date == trade_date,
                        SpotPrice.region == region,
                    )
                    .first()
                )
                values = {
                    "price": round(price + REGIONAL_SPOT_OFFSETS[region], 2),
                    "source": SPOT_SOURCE_TAG if region == "华东" else f"{SPOT_SOURCE_TAG}:regional-estimate",
                }
                if existing:
                    for key, value in values.items():
                        setattr(existing, key, value)
                else:
                    db.add(
                        SpotPrice(
                            product_code=product.code,
                            trade_date=trade_date,
                            region=region,
                            **values,
                        )
                    )
                written += 1
        print(f"  {trade_day}: 累计写入/更新 {written} 条", flush=True)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=140)
    parser.add_argument("--db", default="./future_analysis.db")
    parser.add_argument("--futures-only", action="store_true")
    parser.add_argument("--spot-only", action="store_true")
    args = parser.parse_args()

    os.environ["DATABASE_URL"] = f"sqlite:///{args.db}"
    os.environ.setdefault("SCHEDULER_ENABLED", "false")
    reset_settings_cache()
    database.configure_database(os.environ["DATABASE_URL"])
    # 关键：configure 之后必须从模块取 SessionLocal（导入期 from-import 会绑定旧引擎）
    db = database.SessionLocal()

    products = (
        db.query(Product)
        .filter(Product.is_active.is_(True))
        .order_by(Product.display_order)
        .all()
    )
    run_futures = not args.spot_only
    run_spot = not args.futures_only

    if run_futures:
        print("== 期货回填（主力连续日线）==")
        for product in products:
            if not (product.futures_symbol or "").strip():
                continue
            try:
                written, first, last = backfill_futures_product(db, product, args.days)
                print(f"{product.code}: 写入/更新 {written} 条（{first} ~ {last}）")
            except Exception as exc:
                print(f"{product.code}: 失败 {type(exc).__name__} {exc}")
        db.commit()

    if run_spot:
        print("== 现货回填（futures_spot_price 逐交易日）==")
        try:
            written = backfill_spot(db, products, args.days)
            print(f"现货合计写入/更新 {written} 条")
        except Exception as exc:
            print(f"现货回填失败 {type(exc).__name__} {exc}")
        db.commit()

    db.close()


if __name__ == "__main__":
    main()
