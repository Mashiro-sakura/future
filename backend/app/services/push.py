from __future__ import annotations

from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PushLog, Report, WechatMiniappSubscriber
from app.services.basis import basis_brief_lines
from app.services.reports import mark_report_pushed
from app.services.wechat_miniapp import WechatMiniappApiError, is_wechat_miniapp_subscription_configured, send_subscribe_message


def _brief(text: str, limit: int = 180) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def build_wechat_markdown(report: Report, db: Session | None = None) -> str:
    settings = get_settings()
    lines = [
        f"## {report.title}",
        "",
        f"> 报告状态：{report.status}  生成时间：{report.generated_at:%Y-%m-%d %H:%M}",
        "",
    ]
    urgent_policies = [
        (str(item.get("product_code", "")), _brief(str(item.get("policy", "")), limit=240))
        for item in report.product_analyses
        if "重大供需事件" in str(item.get("policy", ""))
    ]
    if urgent_policies:
        lines.append("### 重大供需事件")
        for code, policy in urgent_policies:
            lines.append(f"- **{code}**：{policy}")
        lines.append("")

    if db is not None:
        basis_lines = basis_brief_lines(db)
        if basis_lines:
            lines.extend(["### 基差结构快照", *basis_lines, ""])

    lines.append("### 采购建议")
    for item in report.recommendations:
        lines.append(f"- **{item.product_code}**：{item.action}（置信度{item.confidence}%）")
        lines.append(f"  {item.basis}")
    if report.product_analyses:
        lines.extend(["", "### 政策/产业消息"])
        for item in report.product_analyses:
            policy = _brief(str(item.get("policy", "")))
            if policy:
                lines.append(f"- **{item.get('product_code', '')}**：{policy}")
    lines.extend(["", "### 行情摘要", report.market_summary, "", f"[查看客户面]({settings.public_client_url})"])
    return "\n".join(lines)


def push_report_to_wechat(db: Session, report: Report) -> tuple[str, str]:
    settings = get_settings()
    if not settings.wechat_work_webhook_url:
        message = "未配置WECHAT_WORK_WEBHOOK_URL，已跳过真实推送"
        db.add(PushLog(report_id=report.id, channel="wechat_work", status="skipped", message=message, sent_at=datetime.utcnow()))
        db.commit()
        return "skipped", message

    payload = {"msgtype": "markdown", "markdown": {"content": build_wechat_markdown(report, db=db)}}
    try:
        response = requests.post(settings.wechat_work_webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("errcode") == 0:
            db.add(
                PushLog(
                    report_id=report.id,
                    channel="wechat_work",
                    status="success",
                    message="企业微信推送成功",
                    sent_at=datetime.utcnow(),
                )
            )
            mark_report_pushed(db, report)
            return "success", "企业微信推送成功"
        message = f"企业微信返回异常：{data}"
        db.add(PushLog(report_id=report.id, channel="wechat_work", status="failed", message=message, sent_at=datetime.utcnow()))
        db.commit()
        return "failed", message
    except Exception as exc:
        message = f"企业微信推送失败：{exc}"
        db.add(PushLog(report_id=report.id, channel="wechat_work", status="failed", message=message, sent_at=datetime.utcnow()))
        db.commit()
        return "failed", message


def push_report_to_miniapp_subscribers(db: Session, report: Report) -> tuple[str, str]:
    if not is_wechat_miniapp_subscription_configured():
        message = "未配置微信小程序订阅消息凭据，已跳过真实推送"
        db.add(PushLog(report_id=report.id, channel="wechat_miniapp", status="skipped", message=message, sent_at=datetime.utcnow()))
        db.commit()
        return "skipped", message

    subscribers = (
        db.query(WechatMiniappSubscriber)
        .filter(
            WechatMiniappSubscriber.is_active.is_(True),
            WechatMiniappSubscriber.subscription_count > 0,
            WechatMiniappSubscriber.template_id == get_settings().wechat_subscribe_template_id,
        )
        .all()
    )
    if not subscribers:
        message = "暂无已授权微信小程序订阅用户，已跳过推送"
        db.add(PushLog(report_id=report.id, channel="wechat_miniapp", status="skipped", message=message, sent_at=datetime.utcnow()))
        db.commit()
        return "skipped", message

    success_count = 0
    failed_count = 0
    for subscriber in subscribers:
        try:
            send_subscribe_message(subscriber.openid, report)
            subscriber.subscription_count = max(0, subscriber.subscription_count - 1)
            subscriber.last_sent_at = datetime.utcnow()
            db.add(
                PushLog(
                    report_id=report.id,
                    channel="wechat_miniapp",
                    status="success",
                    message="微信小程序订阅消息发送成功",
                    sent_at=datetime.utcnow(),
                )
            )
            success_count += 1
        except WechatMiniappApiError as exc:
            if exc.errcode in {40003, 43101, 41030}:
                subscriber.subscription_count = 0
                subscriber.is_active = False
            db.add(
                PushLog(
                    report_id=report.id,
                    channel="wechat_miniapp",
                    status="failed",
                    message=f"微信小程序订阅消息发送失败：{exc}",
                    sent_at=datetime.utcnow(),
                )
            )
            failed_count += 1
        except Exception as exc:
            db.add(
                PushLog(
                    report_id=report.id,
                    channel="wechat_miniapp",
                    status="failed",
                    message=f"微信小程序订阅消息发送失败：{exc}",
                    sent_at=datetime.utcnow(),
                )
            )
            failed_count += 1

    db.commit()
    if success_count:
        mark_report_pushed(db, report)
        return "success", f"微信小程序订阅消息已发送给{success_count}位用户，失败{failed_count}位"
    return "failed", f"微信小程序订阅消息发送失败，共{failed_count}位用户"
