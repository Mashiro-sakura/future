from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta

import requests

from app.config import get_settings
from app.models import Report


class WechatMiniappApiError(RuntimeError):
    def __init__(self, message: str, errcode: int | None = None) -> None:
        super().__init__(message)
        self.errcode = errcode


_token_lock = threading.Lock()
_token_value = ""
_token_expires_at = datetime.min


def reset_wechat_miniapp_token_cache() -> None:
    global _token_value, _token_expires_at
    with _token_lock:
        _token_value = ""
        _token_expires_at = datetime.min


def is_wechat_miniapp_subscription_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.wechat_miniapp_subscribe_enabled
        and settings.wechat_miniapp_appid
        and settings.wechat_miniapp_secret
        and settings.wechat_subscribe_template_id
    )


def _wechat_error(data: object, fallback: str) -> WechatMiniappApiError:
    if isinstance(data, dict):
        errcode = data.get("errcode")
        message = str(data.get("errmsg") or data.get("message") or fallback)
        return WechatMiniappApiError(f"{fallback}: {message}", errcode if isinstance(errcode, int) else None)
    return WechatMiniappApiError(fallback)


def get_access_token() -> str:
    global _token_value, _token_expires_at
    if not is_wechat_miniapp_subscription_configured():
        raise WechatMiniappApiError("未配置微信小程序订阅消息凭据")
    now = datetime.utcnow()
    with _token_lock:
        if _token_value and now < _token_expires_at:
            return _token_value
        settings = get_settings()
        response = requests.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": settings.wechat_miniapp_appid,
                "secret": settings.wechat_miniapp_secret,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise _wechat_error(data, "获取微信小程序访问令牌失败")
        expires_in = int(data.get("expires_in", 7200))
        _token_value = str(token)
        _token_expires_at = now + timedelta(seconds=max(60, expires_in - 300))
        return _token_value


def exchange_code_for_openid(code: str) -> str:
    if not is_wechat_miniapp_subscription_configured():
        raise WechatMiniappApiError("未配置微信小程序订阅消息凭据")
    settings = get_settings()
    response = requests.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": settings.wechat_miniapp_appid,
            "secret": settings.wechat_miniapp_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    openid = data.get("openid") if isinstance(data, dict) else None
    if not openid:
        raise _wechat_error(data, "微信登录凭证校验失败")
    return str(openid)


def _truncate(text: str, limit: int = 20) -> str:
    normalized = " ".join((text or "").split())
    return normalized if len(normalized) <= limit else f"{normalized[: max(0, limit - 1)]}…"


def _template_values(report: Report) -> dict[str, str]:
    first_recommendation = report.recommendations[0].action if report.recommendations else "查看日报"
    session = {"morning": "早报", "evening": "晚报", "urgent": "突发快讯"}.get(report.session_name, "日报")
    published_at = report.published_at or report.generated_at
    return {
        "title": _truncate(report.title),
        "report_date": report.report_date.isoformat(),
        "published_at": published_at.strftime("%Y-%m-%d %H:%M"),
        "session": session,
        "summary": _truncate(report.market_summary, 20),
        "recommendation": _truncate(first_recommendation, 20),
    }


def _format_template_value(value: str, values: dict[str, str]) -> str:
    try:
        return value.format_map(values)
    except (KeyError, ValueError):
        return value


def build_subscribe_message_data(report: Report) -> dict[str, dict[str, str]]:
    settings = get_settings()
    values = _template_values(report)
    if not settings.wechat_subscribe_template_data.strip():
        return {
            "thing1": {"value": values["title"]},
            "time2": {"value": values["published_at"]},
            "thing3": {"value": values["summary"]},
        }
    try:
        raw_data = json.loads(settings.wechat_subscribe_template_data)
    except json.JSONDecodeError as exc:
        raise WechatMiniappApiError("WECHAT_SUBSCRIBE_TEMPLATE_DATA 不是有效 JSON") from exc
    if not isinstance(raw_data, dict) or not raw_data:
        raise WechatMiniappApiError("WECHAT_SUBSCRIBE_TEMPLATE_DATA 必须是非空 JSON 对象")

    formatted: dict[str, dict[str, str]] = {}
    for field_name, field_value in raw_data.items():
        if isinstance(field_value, str):
            formatted[str(field_name)] = {"value": _format_template_value(field_value, values)}
        elif isinstance(field_value, dict) and isinstance(field_value.get("value"), str):
            entry = {str(key): str(value) for key, value in field_value.items()}
            entry["value"] = _format_template_value(str(field_value["value"]), values)
            formatted[str(field_name)] = entry
        else:
            raise WechatMiniappApiError("订阅模板字段的值必须为字符串或包含 value 的对象")
    return formatted


def build_subscribe_message_payload(openid: str, report: Report) -> dict[str, object]:
    settings = get_settings()
    try:
        page = settings.wechat_subscribe_page.format(report_id=report.id)
    except (KeyError, ValueError):
        page = settings.wechat_subscribe_page
    payload: dict[str, object] = {
        "touser": openid,
        "template_id": settings.wechat_subscribe_template_id,
        "page": page,
        "data": build_subscribe_message_data(report),
        "lang": "zh_CN",
    }
    if settings.wechat_miniapp_state in {"developer", "trial", "formal"}:
        payload["miniprogram_state"] = settings.wechat_miniapp_state
    return payload


def send_subscribe_message(openid: str, report: Report) -> None:
    access_token = get_access_token()
    response = requests.post(
        "https://api.weixin.qq.com/cgi-bin/message/subscribe/send",
        params={"access_token": access_token},
        json=build_subscribe_message_payload(openid, report),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("errcode") != 0:
        raise _wechat_error(data, "发送微信小程序订阅消息失败")
