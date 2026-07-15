from __future__ import annotations

from fastapi.testclient import TestClient


class FakeWechatResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


def test_admin_auth_is_required(client: TestClient) -> None:
    response = client.post("/api/admin/data/sync")
    assert response.status_code == 401


def test_sync_generate_publish_and_public_overview(client: TestClient, auth_headers: dict[str, str]) -> None:
    sync_response = client.post("/api/admin/data/sync?days=10", headers=auth_headers)
    assert sync_response.status_code == 200, sync_response.text
    assert sync_response.json()["synced_products"] == 10

    generate_response = client.post("/api/admin/reports/generate?session_name=morning", headers=auth_headers)
    assert generate_response.status_code == 200, generate_response.text
    report = generate_response.json()
    assert report["status"] == "draft"
    assert len(report["recommendations"]) == 10
    assert len(report["product_analyses"]) == 10
    assert report["product_analyses"][0]["product_code"]
    for analysis in report["product_analyses"]:
        if analysis["product_code"] == "OCT":
            assert "现货品种" in analysis["price_behavior"]
            assert "暂不做期货盘面分析" in analysis["price_behavior"]
        else:
            assert "K线/形态" in analysis["price_behavior"]
            assert "均线/多周期" in analysis["price_behavior"]
            assert "持仓量" in analysis["price_behavior"]
            assert "Al Brooks" in analysis["price_behavior"]
            assert "YTC" in analysis["price_behavior"]
        assert "社会库存" in analysis["fundamentals"]
        assert "工厂库存" in analysis["fundamentals"]
        assert "库存周期" in analysis["fundamentals"]
        assert "供需判断" in analysis["fundamentals"]
        assert "区域现货" in analysis["fundamentals"]
        assert "华东" in analysis["fundamentals"]
        assert "华南" in analysis["fundamentals"]
        assert "西南" in analysis["fundamentals"]
        assert "开工率" in analysis["fundamentals"]
        assert "美元兑人民币" in analysis["macro"]
        assert "中国经济" in analysis["macro"]
        assert "美国经济" in analysis["macro"]
        assert "原油" in analysis["macro"]
        assert "产业链传导" in analysis["macro"]
        assert "每日政策/产业消息" in analysis["policy"]
        assert "安全生产" in analysis["policy"]
        assert "环保" in analysis["policy"]
        assert "检修" in analysis["policy"]
        assert analysis["conclusion"].startswith("结论：")
        assert "四维综合评分" in analysis["conclusion"]
    for recommendation in report["recommendations"]:
        assert "四维综合评分" in recommendation["basis"]
        assert "价格行为" in recommendation["basis"]
        assert "基本面" in recommendation["basis"]
        assert "宏观面" in recommendation["basis"]
        assert "政策面" in recommendation["basis"]
    assert "主力合约" in report["price_behavior_analysis"]
    assert "Al Brooks" in report["price_behavior_analysis"]
    assert "社会库存" in report["fundamentals_analysis"]
    assert "供需判断" in report["fundamentals_analysis"]
    assert "华东" in report["fundamentals_analysis"]
    assert "华南" in report["fundamentals_analysis"]
    assert "西南" in report["fundamentals_analysis"]
    assert "开工率" in report["fundamentals_analysis"]
    assert report["fundamentals_analysis"]
    assert report["macro_analysis"]
    assert "美元兑人民币" in report["macro_analysis"]
    assert "布伦特原油" in report["macro_analysis"]
    assert "中国PMI" in report["macro_analysis"]
    assert "美国PMI" in report["macro_analysis"]
    assert report["policy_analysis"]
    assert "每日政策/产业消息" in report["policy_analysis"]
    assert "OCT：现货" in report["market_summary"]
    assert "OCT：主力合约" not in report["market_summary"]

    hidden_response = client.get("/api/public/reports/latest")
    assert hidden_response.status_code == 404

    publish_response = client.post(f"/api/admin/reports/{report['id']}/publish", headers=auth_headers)
    assert publish_response.status_code == 200

    reports_response = client.get("/api/public/reports")
    assert reports_response.status_code == 200
    assert reports_response.json()[0]["id"] == report["id"]

    overview_response = client.get("/api/public/overview")
    assert overview_response.status_code == 200, overview_response.text
    overview = overview_response.json()
    assert overview["latest_report"]["id"] == report["id"]
    assert {item["code"] for item in overview["products"]} == {
        "PTA",
        "PVC",
        "LLDPE",
        "PP",
        "PB",
        "P",
        "PL",
        "PX",
        "CU",
        "OCT",
    }
    assert all(item["futures_contract"] for item in overview["products"] if item["code"] != "OCT")
    oct_item = next(item for item in overview["products"] if item["code"] == "OCT")
    assert oct_item["futures_contract"] is None
    assert oct_item["futures_close"] is None
    assert oct_item["basis_value"] is None


def test_urgent_supply_demand_event_can_be_pushed(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/api/admin/data/sync?days=5", headers=auth_headers)
    response = client.post(
        "/api/admin/policy-events",
        headers=auth_headers,
        json={
            "product_codes": ["PVC"],
            "category": "供需突发",
            "title": "华东PVC装置突发停车",
            "content": "华东主力装置临停，短期供应收缩并可能改变区域供需平衡，需跟踪社会库存、工厂库存和开工率。",
            "impact_level": "重大关注",
            "source": "manual-test",
            "push_now": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 1
    assert payload["report_id"]
    assert payload["push_status"] == "skipped"

    latest_response = client.get("/api/public/reports/latest")
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["session_name"] == "urgent"
    assert "突发快讯" in latest["title"]
    assert "重大供需事件" in latest["policy_analysis"]
    pvc_analysis = next(item for item in latest["product_analyses"] if item["product_code"] == "PVC")
    assert "华东PVC装置突发停车" in pvc_analysis["policy"]
    assert "影响供需平衡" in latest["policy_analysis"]


def test_spot_csv_import_and_trend(client: TestClient, auth_headers: dict[str, str]) -> None:
    csv_content = "product_code,trade_date,price,region\nPTA,2026-07-08,5900,华东\n"
    response = client.post(
        "/api/admin/import/spot",
        headers=auth_headers,
        files={"file": ("spot.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 1

    client.post("/api/admin/data/sync?days=5", headers=auth_headers)
    trend_response = client.get("/api/public/products/PTA/trend?days=7")
    assert trend_response.status_code == 200
    assert trend_response.json()
    assert "futures_contract" in trend_response.json()[-1]

    oct_trend_response = client.get("/api/public/products/OCT/trend?days=7")
    assert oct_trend_response.status_code == 200
    oct_points = oct_trend_response.json()
    assert oct_points
    assert oct_points[-1]["spot_price"] is not None
    assert oct_points[-1]["futures_close"] is None


def test_miniapp_subscription_is_saved_and_consumed_by_push(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setenv("WECHAT_MINIAPP_APPID", "wx-test-appid")
    monkeypatch.setenv("WECHAT_MINIAPP_SECRET", "test-secret")
    monkeypatch.setenv("WECHAT_SUBSCRIBE_TEMPLATE_ID", "template-test")
    monkeypatch.setenv("WECHAT_MINIAPP_STATE", "developer")

    from app.config import reset_settings_cache
    from app.database import SessionLocal
    from app.models import WechatMiniappSubscriber
    from app.services.wechat_miniapp import reset_wechat_miniapp_token_cache

    reset_settings_cache()
    reset_wechat_miniapp_token_cache()

    def fake_get(url: str, **kwargs):
        if "jscode2session" in url:
            assert kwargs["params"]["js_code"] == "login-code"
            return FakeWechatResponse({"openid": "openid-test"})
        assert "cgi-bin/token" in url
        return FakeWechatResponse({"access_token": "access-token", "expires_in": 7200})

    def fake_post(url: str, **kwargs):
        assert "message/subscribe/send" in url
        assert kwargs["params"]["access_token"] == "access-token"
        payload = kwargs["json"]
        assert payload["touser"] == "openid-test"
        assert payload["template_id"] == "template-test"
        assert payload["page"].startswith("pages/report/detail?id=")
        return FakeWechatResponse({"errcode": 0, "msgid": 123})

    monkeypatch.setattr("app.services.wechat_miniapp.requests.get", fake_get)
    monkeypatch.setattr("app.services.wechat_miniapp.requests.post", fake_post)

    config_response = client.get("/api/public/wechat/subscribe-config")
    assert config_response.status_code == 200
    assert config_response.json()["enabled"] is True
    assert config_response.json()["template_id"] == "template-test"

    subscribe_response = client.post(
        "/api/public/wechat/subscriptions",
        json={"code": "login-code", "template_id": "template-test"},
    )
    assert subscribe_response.status_code == 200, subscribe_response.text
    assert subscribe_response.json()["subscription_count"] == 1

    client.post("/api/admin/data/sync?days=5", headers=auth_headers)
    report = client.post("/api/admin/reports/generate?session_name=morning", headers=auth_headers).json()
    push_response = client.post(f"/api/admin/reports/{report['id']}/push", headers=auth_headers)
    assert push_response.status_code == 200, push_response.text
    assert push_response.json()["status"] == "success"
    assert "小程序订阅消息" in push_response.json()["message"]

    db = SessionLocal()
    try:
        subscriber = db.query(WechatMiniappSubscriber).filter(WechatMiniappSubscriber.openid == "openid-test").one()
        assert subscriber.subscription_count == 0
        assert subscriber.last_sent_at is not None
    finally:
        db.close()

    logs_response = client.get("/api/admin/logs", headers=auth_headers)
    assert logs_response.status_code == 200
    assert any(
        item["channel"] == "wechat_miniapp" and item["status"] == "success"
        for item in logs_response.json()["push_logs"]
    )
