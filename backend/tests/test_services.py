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
    # 采购建议段仍在基差段之后（结构先行，行动在后）
    assert markdown.index("### 基差结构快照") < markdown.index("### 采购建议")
