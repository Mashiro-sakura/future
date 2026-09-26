"""波动率历史回填脚本——逐交易日抓郑商所期权日行情，回填 volatility_daily。

为什么单独写：IV 分位需要约一年历史（252 交易日），sync 链路只补近 5 天。
一次性回填，先入副本库验证再动正式库（SessionLocal 绑定坑见 backfill_history.py）。

用法：
  python scripts/backfill_volatility.py [--days 370] [--db PATH] [--code PTA]
默认 db=./future_analysis.db。--days 用自然日（脚本自动跳过周末与非交易日），
370 自然日 ≈ 250 交易日，刚好铺满一年分位窗口。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from datetime import date, timedelta

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import reset_settings_cache  # noqa: E402
import app.database as database  # noqa: E402  （必须模块级 import，防导入期绑定旧引擎）
from app.models import Product, VolatilityDaily  # noqa: E402
from app.services.volatility import OPTION_PRODUCTS, sync_volatility_for_date  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=370, help="回填自然日数（自动跳过周末/非交易日）")
    parser.add_argument("--db", default="./future_analysis.db")
    parser.add_argument("--code", default=None, help="只回填指定品种（默认全部期权品种）")
    parser.add_argument("--sleep", type=float, default=0.6, help="每次请求间隔秒数，防打爆交易所")
    args = parser.parse_args()

    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.abspath(args.db)}"
    reset_settings_cache()
    database.configure_database(os.environ["DATABASE_URL"])
    database.init_db()  # configure_database 只建引擎不建表，create_all 在 init_db 里
    db = database.SessionLocal()

    codes = [args.code.upper()] if args.code else list(OPTION_PRODUCTS)
    products = db.query(Product).filter(Product.code.in_(codes)).all()
    if not products:
        print(f"未找到品种: {codes}")
        return

    today = date.today()
    written = skipped = empty = 0
    for offset in range(args.days):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            skipped += 1
            continue
        for product in products:
            try:
                record = sync_volatility_for_date(db, product, day)
            except Exception as exc:  # 单日失败不连坐
                print(f"[{day}] {product.code} 异常: {exc}")
                record = None
            if record is None:
                empty += 1
            else:
                written += 1
            time.sleep(args.sleep)
        if offset % 20 == 0:
            db.commit()
            print(f"[{day}] 进度 offset={offset} 已写入{written} 非交易日/空{empty}")
    db.commit()

    total = db.query(VolatilityDaily).filter(VolatilityDaily.product_code.in_(codes)).count()
    span = (
        db.query(VolatilityDaily.trade_date)
        .filter(VolatilityDaily.product_code.in_(codes))
        .order_by(VolatilityDaily.trade_date)
        .first()
    )
    print(f"完成: 本次写入/更新 {written} 条，空 {empty}，库内累计 {total} 条，最早 {span[0] if span else '-'}")
    db.close()


if __name__ == "__main__":
    main()
