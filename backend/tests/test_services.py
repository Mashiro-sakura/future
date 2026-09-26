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
