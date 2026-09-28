"""席位持仓历史回填——逐交易日抓交易所分席位前20榜，回填 seat_position_daily。

白名单快照层需要至少 2 个交易日（最新+前值算 net_chg_1d）。
SessionLocal 绑定坑与 init_db 坑见 backfill_history.py。

用法：
  python scripts/backfill_seat_rank.py [--days 60] [--db PATH] [--code PTA]
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
from app.models import Product, SeatPositionDaily  # noqa: E402
from app.services.seat_rank import SEAT_PRODUCTS, sync_seat_rank_for_date  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=60, help="回填自然日数（自动跳过周末/非交易日）")
    parser.add_argument("--db", default="./future_analysis.db")
    parser.add_argument("--code", default=None)
    parser.add_argument("--sleep", type=float, default=0.8)
    args = parser.parse_args()

    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.abspath(args.db)}"
    reset_settings_cache()
    database.configure_database(os.environ["DATABASE_URL"])
    database.init_db()  # configure_database 只建引擎不建表，create_all 在 init_db 里
    db = database.SessionLocal()

    codes = [args.code.upper()] if args.code else list(SEAT_PRODUCTS)
    products = db.query(Product).filter(Product.code.in_(codes)).all()
    if not products:
        print(f"未找到品种: {codes}")
        return

    today = date.today()
    written_days = empty = 0
    for offset in range(args.days):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        for product in products:
            try:
                n = sync_seat_rank_for_date(db, product, day)
            except Exception as exc:  # 单日失败不连坐
                print(f"[{day}] {product.code} 异常: {exc}")
                n = 0
            if n > 0:
                written_days += 1
            else:
                empty += 1
            time.sleep(args.sleep)
        if offset % 20 == 0:
            db.commit()
            print(f"[{day}] 进度 offset={offset} 有效品种日{written_days} 空{empty}")
    db.commit()

    total = db.query(SeatPositionDaily).filter(SeatPositionDaily.product_code.in_(codes)).count()
    span = (
        db.query(SeatPositionDaily.trade_date)
        .filter(SeatPositionDaily.product_code.in_(codes))
        .order_by(SeatPositionDaily.trade_date)
        .first()
    )
    print(f"完成: 有效品种日 {written_days}，空 {empty}，库内席位行累计 {total} 条，最早 {span[0] if span else '-'}")
    db.close()


if __name__ == "__main__":
    main()
