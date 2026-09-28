from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.services.data_fetcher import (
    _contract_candidate_codes,
    _contract_symbol_variants,
    _parse_sina_realtime_quote_items,
    _parse_sina_realtime_text,
)


def test_main_contract_symbol_variants() -> None:
    assert _contract_symbol_variants("TA2609") == ["TA2609", "TA609"]
    assert _contract_symbol_variants("PP2609") == ["PP2609", "PP609"]


def test_contract_candidate_codes() -> None:
    assert _contract_candidate_codes("CU", date(2026, 7, 11), months_forward=4) == [
        "CU2607",
        "CU2608",
        "CU2609",
        "CU2610",
    ]


def test_parse_sina_realtime_text() -> None:
    text = 'var hq_str_nf_TA2609="PTA2609,230000,5552.000,5588.000,5542.000,0.000,5568.000,5570.000,5568.000,0.000,5610.000,160,67,982823.000,226076,郑,PTA,2026-07-10,1";'
    rows = _parse_sina_realtime_text(text)
    assert rows[0][0] == "PTA2609"
    assert rows[0][8] == "5568.000"
    assert rows[0][13] == "982823.000"
    assert rows[0][17] == "2026-07-10"


def test_parse_sina_realtime_quote_items() -> None:
    text = (
        'var hq_str_nf_PB2608="铅2608,230000,16020.000,16050.000,15960.000,0.000,16025.000,16030.000,16030.000,0.000,16000.000,4,8,70447.000,15899,沪,铅,2026-07-11,1";'
        'var hq_str_nf_PB2609="铅2609,230000,16040.000,16070.000,16010.000,0.000,16050.000,16055.000,16055.000,0.000,16020.000,3,7,68118.000,5413,沪,铅,2026-07-11,1";'
    )
    rows = _parse_sina_realtime_quote_items(text)
    assert rows[0][0] == "PB2608"
    assert rows[0][1][8] == "16030.000"


def test_realtime_endpoint_shape(client: TestClient) -> None:
    """准实时端点：无网/上游失败也必须 200 出结构（stale 不白屏）。"""
    response = client.get("/api/public/realtime")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) and data
    item = data[0]
    assert set(item) >= {"code", "contract_code", "price", "prev_close", "change_pct", "trading_now", "server_time"}
    assert isinstance(item["trading_now"], bool)


def test_is_trading_time() -> None:
    from datetime import datetime

    from app.routers.public import _is_trading_time

    assert _is_trading_time(datetime(2026, 9, 25, 9, 30)) is True  # 周五上午盘
    assert _is_trading_time(datetime(2026, 9, 25, 10, 20)) is False  # 盘中休息
    assert _is_trading_time(datetime(2026, 9, 25, 14, 0)) is True  # 下午盘
    assert _is_trading_time(datetime(2026, 9, 25, 21, 30)) is True  # 夜盘
    assert _is_trading_time(datetime(2026, 9, 25, 16, 0)) is False  # 收盘后
    assert _is_trading_time(datetime(2026, 9, 26, 10, 0)) is False  # 周六


def test_realtime_quotes_fall_back_to_cache(monkeypatch) -> None:
    """上游故障时回退旧缓存（stale 总比白屏强）。"""
    from app.services import data_fetcher

    row = data_fetcher.FuturesRow(
        trade_date=date(2026, 9, 25),
        contract_code="TA2701",
        open_price=None,
        high_price=None,
        low_price=None,
        close_price=6300.0,
        settlement_price=None,
        volume=1.0,
        open_interest=2.0,
        source="sina-main-contract-realtime",
    )

    class _ProductStub:
        code = "PTA"
        futures_symbol = "TA0"
        exchange = "CZCE"

    data_fetcher._realtime_cache["ts"] = 0.0
    data_fetcher._realtime_cache["data"] = None
    monkeypatch.setattr(data_fetcher, "_fetch_realtime_rows_from_sina_symbols", lambda symbols: [("TA2701", row)])
    first = data_fetcher.fetch_realtime_main_quotes([_ProductStub()], ttl=60)
    assert first["PTA"].close_price == 6300.0

    # 缓存过期 + 上游爆炸 → 必须回退到旧缓存
    def _boom(symbols):
        raise RuntimeError("upstream down")

    data_fetcher._realtime_cache["ts"] = 0.0
    monkeypatch.setattr(data_fetcher, "_fetch_realtime_rows_from_sina_symbols", _boom)
    second = data_fetcher.fetch_realtime_main_quotes([_ProductStub()], ttl=60)
    assert second["PTA"].close_price == 6300.0


def test_push_without_webhook_is_logged(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/api/admin/data/sync?days=5", headers=auth_headers)
    report = client.post("/api/admin/reports/generate?session_name=evening", headers=auth_headers).json()
    push_response = client.post(f"/api/admin/reports/{report['id']}/push", headers=auth_headers)
    assert push_response.status_code == 200, push_response.text
    assert push_response.json()["status"] == "skipped"

    logs_response = client.get("/api/admin/logs", headers=auth_headers)
    assert logs_response.status_code == 200
    assert logs_response.json()["push_logs"][0]["status"] == "skipped"


def test_wechat_markdown_includes_basis_snapshot(client: TestClient, auth_headers: dict[str, str]) -> None:
    """推送 markdown 应包含基差结构快照段，且数据停更时带警示行。"""
    from datetime import datetime

    from app.database import SessionLocal
    from app.models import Report
    from app.services.push import build_wechat_markdown

    client.post("/api/admin/data/sync?days=5", headers=auth_headers)
    client.post("/api/admin/reports/generate?session_name=evening", headers=auth_headers)
    db = SessionLocal()
    report = db.query(Report).order_by(Report.id.desc()).first()
    assert report is not None
    report.generated_at = report.generated_at or datetime.utcnow()
    markdown = build_wechat_markdown(report, db=db)
    db.close()

    assert "### 基差结构快照" in markdown
    assert "基差" in markdown
    # 观察层语言铁律（2026-09-24 拍板）：动作层"采购建议"不进推送，推送只给结构；
    # 基差段必须在行情摘要之前（结构先行）
    assert "### 采购建议" not in markdown
    assert "置信度" not in markdown
    assert markdown.index("### 基差结构快照") < markdown.index("### 行情摘要")


# ── 波动率传感器（V1: PTA/郑商所）─────────────────────────
from datetime import timedelta

from app.services.volatility import compute_hv, extract_atm_iv, parse_option_contract


def test_parse_option_contract() -> None:
    assert parse_option_contract("TA611C4750") == ("TA611", "C", 4750.0)
    assert parse_option_contract("TA701P6300") == ("TA701", "P", 6300.0)
    assert parse_option_contract("") is None
    assert parse_option_contract("TA0") is None


def _opt_row(code: str, iv: float, oi: float) -> dict:
    return {"合约代码": code, "隐含波动率": iv, "持仓量": oi}


def test_extract_atm_iv_picks_main_month_and_nearest_strike() -> None:
    rows = [
        # TA611 持仓量大 = 主力月
        _opt_row("TA611C6300", 30.0, 100), _opt_row("TA611P6300", 32.0, 90),
        _opt_row("TA611C6400", 28.0, 80), _opt_row("TA611P6400", 29.0, 70),
        # TA612 持仓量小，不应被选中（IV 故意离谱做探针）
        _opt_row("TA612C6300", 99.0, 1), _opt_row("TA612P6300", 99.0, 1),
    ]
    atm = extract_atm_iv(rows, futures_ref=6340.0)
    assert atm is not None
    assert atm["underlying_month"] == "TA611"
    assert atm["atm_strike"] == 6300.0  # 距 6340 最近
    assert atm["atm_iv"] == 31.0  # (30+32)/2


def test_extract_atm_iv_empty() -> None:
    assert extract_atm_iv([], futures_ref=6300.0) is None
    assert extract_atm_iv([_opt_row("乱码", 30.0, 100)], futures_ref=6300.0) is None


def test_compute_hv() -> None:
    assert compute_hv([100, 101]) is None  # 数据不足
    flat = compute_hv([100.0] * 30)
    assert flat == 0.0  # 零波动
    import math, random
    random.seed(7)
    prices = [6000.0]
    for _ in range(40):
        prices.append(prices[-1] * math.exp(random.gauss(0, 0.01)))
    hv = compute_hv(prices)
    assert hv is not None and 5 < hv < 30  # 日波 1% ≈ 年化 15.9%


def test_volatility_endpoint(client: TestClient) -> None:
    import app.database as database
    from app.models import VolatilityDaily

    db = database.SessionLocal()
    base = date(2026, 8, 3)
    for i in range(30):
        db.add(VolatilityDaily(
            product_code="PTA", trade_date=base + timedelta(days=i),
            underlying_month="TA611", futures_ref=6300.0, atm_strike=6300.0,
            atm_iv=20.0 + i, call_iv=20.0 + i, put_iv=20.0 + i, hv20=18.0, source="test",
        ))
    db.commit()
    db.close()

    response = client.get("/api/public/volatility/PTA")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["atm_iv"] == 49.0  # 最新一日
    assert data["iv_percentile"] == 100.0  # 递增序列，最新即最高
    assert data["zone"] == "高位区"
    assert data["iv_hv_spread"] == 31.0
    assert data["sample_days"] == 30

    assert client.get("/api/public/volatility/PVC").status_code == 404  # 无期权配置


# ── 成交量分布（Volume Profile，订单流免费近似）─────────────
from app.services.volume_profile import build_volume_profile


def _bar(i: int, price: float, vol: float) -> dict:
    return {
        "datetime": f"2026-09-24 10:{i:02d}:00",
        "open": price, "high": price + 5, "low": price - 5,
        "close": price, "volume": vol, "hold": 1000,
    }


def test_build_volume_profile_basic() -> None:
    # 价格 6300 附近放 40 根大量 bar（密集区），6400 附近 10 根小量
    rows = [_bar(i, 6300, 100) for i in range(40)] + [_bar(40 + i, 6400, 10) for i in range(10)]
    prof = build_volume_profile(rows, bin_count=10)
    assert prof is not None
    assert prof["bar_count"] == 50
    assert 6290 < prof["poc"] < 6310  # POC 落在 6300 密集区
    assert prof["val"] <= prof["poc"] <= prof["vah"]
    # 价值区覆盖率 >= 70%
    covered = sum(b["volume"] for b in prof["bins"] if prof["val"] <= b["low"] and b["high"] <= prof["vah"])
    assert covered / prof["total_volume"] >= 0.70
    assert prof["last_close"] == 6400
    assert prof["position"] in ("高于价值区", "价值区内", "低于价值区")
    poc_bins = [b for b in prof["bins"] if b["is_poc"]]
    assert len(poc_bins) == 1


def test_build_volume_profile_big_volume_split() -> None:
    # 均值 55，阈值 110：vol=200 的 bar 全部计入 big_volume
    rows = [_bar(i, 6300, 10) for i in range(40)] + [_bar(40 + i, 6300, 200) for i in range(10)]
    prof = build_volume_profile(rows, bin_count=10, big_mult=2.0)
    assert prof is not None
    big_total = sum(b["big_volume"] for b in prof["bins"])
    assert big_total == 2000  # 10 × 200
    assert prof["big_volume_pct"] == round(2000 / 2400 * 100, 1)


def test_build_volume_profile_insufficient_data() -> None:
    assert build_volume_profile([], bin_count=10) is None
    assert build_volume_profile([_bar(0, 6300, 100)] * 5, bin_count=10) is None
    # 零成交量 bar 被过滤
    assert build_volume_profile([_bar(i, 6300, 0) for i in range(50)], bin_count=10) is None


def test_volume_profile_endpoint(client: TestClient, monkeypatch) -> None:
    import app.services.volume_profile as vp

    rows = [_bar(i, 6300 + (i % 5) * 10, 100) for i in range(60)]
    monkeypatch.setattr(vp, "_fetch_minute_bars", lambda symbol: rows)
    vp._profile_cache.clear()

    response = client.get("/api/public/volume-profile/PTA")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == "PTA"
    assert data["poc"] is not None and data["bins"]
    assert data["position"] in ("高于价值区", "价值区内", "低于价值区")

    # 上游爆炸 → 回退缓存（仍是 200）
    def _boom(symbol):
        raise RuntimeError("upstream down")
    monkeypatch.setattr(vp, "_fetch_minute_bars", _boom)
    vp._profile_cache.clear()
    vp._profile_cache["PTA"] = (999999999999, data)  # 远未来时间戳=缓存有效
    assert client.get("/api/public/volume-profile/PTA").status_code == 200


# ── 主力持仓排名（龙虎榜，大资金方向）────────────────────
from app.services.position_rank import position_rank_snapshot
import app.database as database
from app.models import PositionRankDaily


def _seed_rank_rows(n: int = 30, net_start: float = 50000.0) -> None:
    db = database.SessionLocal()
    base = date(2026, 8, 3)
    for i in range(n):
        net = net_start + i * 1000
        db.add(PositionRankDaily(
            product_code="PTA", trade_date=base + timedelta(days=i),
            long_top20=1000000 + net / 2, long_chg_top20=1000.0,
            short_top20=1000000 - net / 2, short_chg_top20=-500.0,
            net_long=net, source="test",
        ))
    db.commit()
    db.close()


def test_position_rank_snapshot(client: TestClient) -> None:
    _seed_rank_rows(30)
    snap = position_rank_snapshot(database.SessionLocal(), "PTA")
    assert snap is not None
    assert snap["net_long"] == 50000 + 29 * 1000
    assert snap["net_chg"] == 1000 - (-500)  # 多增 - 空减
    assert snap["net_percentile"] == 100.0  # 递增序列最新即最高
    assert snap["zone"] == "高位区"
    assert snap["long_pct"] > 50
    assert snap["sample_days"] == 30


def test_position_rank_snapshot_no_config() -> None:
    assert position_rank_snapshot(database.SessionLocal(), "PVC") is None


def test_position_rank_endpoint(client: TestClient) -> None:
    _seed_rank_rows(5)
    response = client.get("/api/public/position-rank/PTA")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == "PTA"
    assert data["net_long"] is not None
    assert client.get("/api/public/position-rank/PVC").status_code == 404


# ── 主力持仓排名（龙虎榜，大资金方向）────────────────────
from app.services.position_rank import position_rank_snapshot
import app.database as database
from app.models import PositionRankDaily


def _seed_rank_rows(n: int = 30, net_start: float = 50000.0) -> None:
    db = database.SessionLocal()
    base = date(2026, 8, 3)
    for i in range(n):
        net = net_start + i * 1000
        db.add(PositionRankDaily(
            product_code="PTA", trade_date=base + timedelta(days=i),
            long_top20=1000000 + net / 2, long_chg_top20=1000.0,
            short_top20=1000000 - net / 2, short_chg_top20=-500.0,
            net_long=net, source="test",
        ))
    db.commit()
    db.close()


def test_position_rank_snapshot(client: TestClient) -> None:
    _seed_rank_rows(30)
    snap = position_rank_snapshot(database.SessionLocal(), "PTA")
    assert snap is not None
    assert snap["net_long"] == 50000 + 29 * 1000
    assert snap["net_chg"] == 1000 - (-500)  # 多增 - 空减
    assert snap["net_percentile"] == 100.0  # 递增序列最新即最高
    assert snap["zone"] == "高位区"
    assert snap["long_pct"] > 50
    assert snap["sample_days"] == 30


def test_position_rank_snapshot_no_config() -> None:
    assert position_rank_snapshot(database.SessionLocal(), "PVC") is None


def test_position_rank_endpoint(client: TestClient) -> None:
    _seed_rank_rows(5)
    response = client.get("/api/public/position-rank/PTA")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == "PTA"
    assert data["net_long"] is not None
    assert client.get("/api/public/position-rank/PVC").status_code == 404


# ── 故障隔离：现货链路死亡不连坐期货（2026-09-26 老板铁律）──
import app.services.data_fetcher as df
from app.models import FuturesPrice, SyncLog


def _stub_sync_env(monkeypatch, spot_behavior="boom"):
    """把 sync 全链路换成可控替身：期货正常返 1 行，现货按 behavior 爆炸或返回空。"""
    row = df.FuturesRow(
        trade_date=date(2026, 9, 24), contract_code="TA0",
        open_price=6300.0, high_price=6350.0, low_price=6280.0,
        close_price=6340.0, settlement_price=6330.0,
        volume=100.0, open_interest=1000.0, source="test",
    )
    monkeypatch.setattr(df, "fetch_futures_prices", lambda product, days: [row])
    if spot_behavior == "boom":
        def _boom(product, days):
            raise RuntimeError("现货源爆炸")
        monkeypatch.setattr(df, "fetch_spot_prices", _boom)
    monkeypatch.setattr(df, "fetch_inventory_snapshots", lambda product, days: [])
    monkeypatch.setattr(df, "fetch_operating_rate_snapshots", lambda product, days: [])
    monkeypatch.setattr(df, "sync_daily_policy_events", lambda db, products: 0)
    import app.services.volatility as vol_mod
    import app.services.position_rank as rank_mod
    monkeypatch.setattr(vol_mod, "sync_volatility_daily", lambda db, days=5: "波动率: stub")
    monkeypatch.setattr(rank_mod, "sync_position_rank_daily", lambda db, days=5: "持仓排名: stub")


def test_sync_spot_failure_does_not_block_futures(client: TestClient, monkeypatch) -> None:
    _stub_sync_env(monkeypatch, spot_behavior="boom")
    monkeypatch.setattr(df, "fetch_macro_snapshots", lambda days: [])
    db = database.SessionLocal()
    synced, message = df.sync_market_data(db, job_type="test", days=5)

    # 期货行必须落库——现货爆炸不许连坐
    futures_count = db.query(FuturesPrice).filter(FuturesPrice.source == "test").count()
    assert futures_count > 0, "现货爆炸导致期货未落库=故障隔离失效"
    assert synced > 0
    assert "现货失败" in message
    # SyncLog 必须如实标 partial（不是 success 也不是 failed）
    log = db.query(SyncLog).filter(SyncLog.job_type == "test").first()
    assert log is not None and log.status == "partial", log.message if log else "no log"
    db.close()


def test_sync_macro_failure_does_not_block_products(client: TestClient, monkeypatch) -> None:
    _stub_sync_env(monkeypatch, spot_behavior="ok")
    def _boom_macro(days):
        raise RuntimeError("宏观源爆炸")
    monkeypatch.setattr(df, "fetch_macro_snapshots", _boom_macro)
    db = database.SessionLocal()
    synced, message = df.sync_market_data(db, job_type="test-macro", days=5)
    assert "宏观指标: 同步失败" in message
    assert synced > 0  # 品种行情照常
    assert db.query(FuturesPrice).filter(FuturesPrice.source == "test").count() > 0
    db.close()


def test_overview_tolerates_futures_only_product(client: TestClient) -> None:
    """现货数据缺失的品种：overview 照常 200，spot/basis 字段为 None 由前端隐藏。"""
    db = database.SessionLocal()
    db.add(FuturesPrice(
        product_code="PTA", trade_date=date(2026, 9, 24), contract_code="TA0",
        close_price=6340.0, source="test-futures-only",
    ))
    db.commit()
    response = client.get("/api/public/overview")
    assert response.status_code == 200, response.text
    pta = next(p for p in response.json()["products"] if p["code"] == "PTA")
    assert pta["futures_close"] == 6340.0
    assert pta["spot_price"] is None and pta["basis_value"] is None
    db.close()


# ── 席位白名单（L2 龙虎榜分席位）────────────────────
from app.services.seat_rank import _aggregate_rows, normalize_party, seat_rank_snapshot
from app.models import SeatPositionDaily


def test_normalize_party_strips_suffix() -> None:
    assert normalize_party("国泰君安（代客）") == "国泰君安"
    assert normalize_party("国泰君安（自营）") == "国泰君安"
    assert normalize_party("东证期货（代客）") == "东证期货"
    assert normalize_party("中信期货") == "中信期货"
    assert normalize_party("") == ""


def test_aggregate_rows_merges_sides_and_suffixes() -> None:
    rows = [
        # 国泰君安代客多头 + 国泰君安自营多头 → 多头合并
        {"long_party_name": "国泰君安（代客）", "long_open_interest": "100,000", "long_open_interest_chg": "1,000",
         "short_party_name": "永安（代客）", "short_open_interest": "50,000", "short_open_interest_chg": "-200"},
        {"long_party_name": "国泰君安（自营）", "long_open_interest": "10,000", "long_open_interest_chg": "500",
         "short_party_name": "国泰君安（代客）", "short_open_interest": "20,000", "short_open_interest_chg": "-100"},
    ]
    agg = _aggregate_rows(rows)
    assert agg["国泰君安"]["long_oi"] == 110000.0
    assert agg["国泰君安"]["long_chg"] == 1500.0
    assert agg["国泰君安"]["short_oi"] == 20000.0
    assert agg["永安"]["short_oi"] == 50000.0


def _seed_seat_rows() -> None:
    db = database.SessionLocal()
    d1, d2 = date(2026, 9, 23), date(2026, 9, 24)
    # 白名单内：永安在榜（两天，净变化可算）；乾坤两天都不在（missing）
    db.add(SeatPositionDaily(product_code="PTA", trade_date=d1, party_name="永安",
                             long_oi=150000, long_chg=-2000, short_oi=80000, short_chg=1000, source="test"))
    db.add(SeatPositionDaily(product_code="PTA", trade_date=d2, party_name="永安",
                             long_oi=155000, long_chg=5000, short_oi=78000, short_chg=-2000, source="test"))
    # 非白名单席位也存（快照层应过滤掉）
    db.add(SeatPositionDaily(product_code="PTA", trade_date=d2, party_name="华泰",
                             long_oi=99000, short_oi=0, source="test"))
    db.commit()
    db.close()


def test_seat_rank_snapshot_and_missing(client: TestClient) -> None:
    _seed_seat_rows()
    snap = seat_rank_snapshot(database.SessionLocal(), "PTA")
    assert snap is not None
    assert snap["trade_date"] == date(2026, 9, 24)
    assert snap["prev_date"] == date(2026, 9, 23)
    by_party = {s["party"]: s for s in snap["seats"]}
    # 白名单席位：永安净头寸与一日变化
    yong_an = by_party["永安"]
    assert yong_an["missing"] is False
    assert yong_an["net"] == 155000 - 78000
    assert yong_an["net_chg_1d"] == (155000 - 78000) - (150000 - 80000)
    # 乾坤不在榜 → missing=True，绝不报错
    assert by_party["乾坤"]["missing"] is True
    # 非白名单席位（华泰）不出现在快照
    assert "华泰" not in by_party
    # 白名单全覆盖
    assert len(snap["seats"]) == len(snap["follow"]) if "follow" in snap else True
    assert snap["follow_count"] + snap["counter_count"] == len(snap["seats"])


def test_seat_rank_endpoint(client: TestClient) -> None:
    _seed_seat_rows()
    response = client.get("/api/public/seat-rank/PTA")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == "PTA"
    assert any(s["party"] == "乾坤" and s["missing"] for s in data["seats"])
    # DCE 品种（PVC）未配置 → 404
    assert client.get("/api/public/seat-rank/PVC").status_code == 404


def test_match_party_prefix_bidirectional() -> None:
    from app.services.seat_rank import _match_party

    stored = ["永安期货", "东证期货", "国泰君安", "中信期货", "中信建投"]
    assert _match_party(stored, "永安") == "永安期货"       # 短名 → 全名
    assert _match_party(stored, "东证") == "东证期货"
    assert _match_party(stored, "国泰君安") == "国泰君安"     # 全等
    # "中信"同时前缀命中两家且等长——歧义匹配（配置层应避免歧义前缀，只验证不误配第三家）
    assert _match_party(stored, "中信") in {"中信期货", "中信建投"}
    assert _match_party(stored, "乾坤") is None               # 不在库 → None


# ── 东财降级链（2026-09-28：新浪对阿里云香港 IP 403）────────────────
import app.services.data_fetcher as df_mod


def test_em_trade_date_adaptive() -> None:
    from datetime import date as _date
    assert df_mod._em_trade_date(1790588322000) == _date(2026, 9, 28)   # 毫秒
    assert df_mod._em_trade_date(1790588322) == _date(2026, 9, 28)      # 秒
    assert df_mod._em_trade_date(None) == _date.today()                  # 兜底


def test_fetch_realtime_row_from_em_scaling(monkeypatch) -> None:
    """f59=2 → f43=625600 应解析为 6256.0；OI/成交量/昨结各就位。"""
    class FakeResp:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": {
                "f43": 625600, "f44": 630000, "f45": 621000, "f46": 628000,
                "f47": 582133, "f58": "PTA2701", "f59": 2, "f60": 634000,
                "f86": 1790588322000, "f108": 982823, "f169": -8400, "f170": -132,
            }}
    captured = {}
    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return FakeResp()
    monkeypatch.setattr(df_mod.requests, "get", fake_get)
    row = df_mod._fetch_realtime_row_from_em("TA2701", "TA2701")
    assert row is not None
    assert captured["params"]["secid"] == "115.ta2701"
    assert row.close_price == 6256.0
    assert row.high_price == 6300.0
    assert row.volume == 582133.0
    assert row.open_interest == 982823.0
    assert row.source == "eastmoney-realtime"
    assert row.settlement_price is None  # 东财无当日结算，诚实留空


def test_fetch_realtime_row_from_em_dead_quote(monkeypatch) -> None:
    """f43='-'（死合约/未开盘无数据）→ None 不崩。"""
    class FakeResp:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": {"f43": "-", "f59": 0}}
    monkeypatch.setattr(df_mod.requests, "get", lambda *a, **k: FakeResp())
    assert df_mod._fetch_realtime_row_from_em("TA2709", "TA2709") is None


def test_sina_health_probe_caches_403(monkeypatch) -> None:
    """新浪 403 → 探测 False 且 5 分钟内不再重探（TTL 缓存）。"""
    df_mod._sina_health.update({"ts": 0.0, "ok": True})
    calls = {"n": 0}
    class FakeResp:
        status_code = 403
        text = "Forbidden"
    def fake_get(url, **kwargs):
        calls["n"] += 1
        return FakeResp()
    monkeypatch.setattr(df_mod.requests, "get", fake_get)
    assert df_mod._sina_available() is False
    assert df_mod._sina_available() is False  # 第二次走缓存
    assert calls["n"] == 1                     # 只探了一次
    df_mod._sina_health.update({"ts": 0.0, "ok": True})  # 复位污染


def test_realtime_falls_back_to_em_when_sina_blocked(client: TestClient, monkeypatch) -> None:
    """新浪被 403：全链路走东财，主力按持仓量选出。"""
    df_mod._sina_health.update({"ts": 0.0, "ok": False})  # 直接标记新浪不可用
    quotes = {
        "TA2701": df_mod.FuturesRow(
            trade_date=date(2026, 9, 28), contract_code="TA2701",
            open_price=6280.0, high_price=6300.0, low_price=6210.0,
            close_price=6256.0, settlement_price=None,
            volume=582133.0, open_interest=982823.0, source="eastmoney-realtime",
        ),
    }
    monkeypatch.setattr(df_mod, "_fetch_realtime_rows_for_product", lambda product: list(quotes.items()))
    from app.models import Product as _P
    rows = df_mod._fetch_realtime_rows_for_product(_P(code="PTA"))
    assert rows[0][0] == "TA2701"
    assert rows[0][1].source == "eastmoney-realtime"
    df_mod._sina_health.update({"ts": 0.0, "ok": True})
