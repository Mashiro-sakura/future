from __future__ import annotations

import json
import math
from datetime import date, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Product, Recommendation, Report
from app.services.analytics import build_analysis_conclusion, build_recommendation, calculate_metrics
from app.services.fundamentals import build_fundamental_view
from app.services.macro import build_macro_overview, build_macro_view
from app.services.policy_events import build_policy_view, sync_daily_policy_events
from app.services.price_action import build_price_behavior_view


def _missing_analysis(report: Report) -> bool:
    return not all(
        [
            report.price_behavior_analysis,
            report.fundamentals_analysis,
            report.macro_analysis,
            report.policy_analysis,
            report.product_analyses,
        ]
    )


def _needs_price_action_upgrade(report: Report) -> bool:
    analysis_text = report.price_behavior_analysis or ""
    analysis_text += "\n".join(str(item.get("price_behavior", "")) for item in report.product_analyses)
    return not all(marker in analysis_text for marker in ["K线/形态", "Al Brooks", "YTC", "均线/多周期"])


def _needs_fundamental_upgrade(report: Report) -> bool:
    analysis_text = report.fundamentals_analysis or ""
    analysis_text += "\n".join(str(item.get("fundamentals", "")) for item in report.product_analyses)
    return not all(marker in analysis_text for marker in ["区域现货", "华东", "华南", "西南", "社会库存", "工厂库存", "库存周期", "供需判断"])


def _needs_macro_upgrade(report: Report) -> bool:
    analysis_text = report.macro_analysis or ""
    analysis_text += "\n".join(str(item.get("macro", "")) for item in report.product_analyses)
    return not all(marker in analysis_text for marker in ["美元兑人民币", "中国经济", "美国经济", "原油", "产业链传导"])


def _needs_policy_upgrade(report: Report) -> bool:
    analysis_text = report.policy_analysis or ""
    analysis_text += "\n".join(str(item.get("policy", "")) for item in report.product_analyses)
    return not all(marker in analysis_text for marker in ["每日政策/产业消息", "安全生产", "环保", "检修"])


def _needs_conclusion_upgrade(report: Report) -> bool:
    return not all(str(item.get("conclusion", "")).startswith("结论：") for item in report.product_analyses)


def _needs_recommendation_upgrade(report: Report) -> bool:
    return not all("四维综合评分" in (item.basis or "") for item in report.recommendations)


def _needs_product_payload_refresh(report: Report, products: list[Product]) -> bool:
    active_codes = {product.code for product in products}
    analysis_codes = {str(item.get("product_code", "")) for item in report.product_analyses}
    return active_codes != analysis_codes


def _product_macro_view(product: Product) -> str:
    if product.code in {"CU", "PB"}:
        return (
            f"{product.code}属于有色金属链条，宏观面重点看美元指数、人民币汇率、海外库存、国内基建与制造业订单。"
            "若工业品风险偏好回落，采购宜更多参考订单覆盖和套保比例。"
        )
    if product.code == "P":
        return "棕榈油宏观面重点看马棕出口、主产区天气、原油和生柴政策，以及油脂油料整体风险偏好。外盘扰动较强时不宜一次性追高补库。"
    if product.code in {"PTA", "PX"}:
        return "芳烃聚酯链条对原油、石脑油、PX/PTA加工费和聚酯开工更敏感，宏观风险偏好会通过成本端放大盘面波动。"
    if product.code in {"PVC", "LLDPE", "PP", "PL"}:
        return "塑化链条重点跟踪原油、煤化工成本、进口窗口、下游开工和终端订单。宏观信号未共振前，采购以刚需和现金流安全为主。"
    return "宏观面重点跟踪大宗商品风险偏好、汇率、成本端和终端需求变化，避免在信号不清晰时大幅抬高库存。"


def _product_policy_view(product: Product, basis: float | None) -> str:
    exchange_note = {
        "SHFE": "关注上期所保证金、限仓、交割仓库与库存规则变化。",
        "DCE": "关注大商所保证金、限仓、交割规则及相关产业政策变化。",
        "CZCE": "关注郑商所保证金、限仓、交割和风控规则变化。",
        "SPOT": "该品种按现货口径跟踪，暂不纳入交易所期货合约风控。",
    }.get(product.exchange, "关注交易所保证金、限仓、交割和风控规则变化。")
    if product.code in {"CU", "PB"}:
        sector_note = "同时跟踪有色金属环保、安全生产、再生资源和进出口政策。"
    elif product.code == "P":
        sector_note = "同时跟踪进口检验、油脂油料储备、生物柴油和主产国出口政策。"
    else:
        sector_note = "同时跟踪能耗、安全生产、环保检查、装置检修和下游行业支持政策。"
    if product.exchange == "SPOT" or not (product.futures_symbol or "").strip():
        basis_note = "政策面更多影响装置开工、进口成本、环保安全检查和下游采购节奏。"
    else:
        basis_note = "当前升水偏高，政策扰动可能带来基差快速回落。" if basis is not None and basis > 80 else "当前基差压力可控，政策面更多作为风险提示项。"
    return f"{exchange_note}{sector_note}{basis_note}"


def _product_fundamental_view(metrics, spot_change: float, basis: float | None) -> str:
    if basis is not None and basis > 80:
        return "现货升水偏高，说明区域流通资源或交付弹性偏紧，采购需关注高价库存风险。"
    if basis is not None and basis < -80:
        return "现货贴水偏深，说明现货承接偏弱或低价资源释放，可关注分批补库窗口。"
    if spot_change < -0.8:
        return "现货价格回落，需求端议价能力阶段性增强，刚需补库可放慢节奏。"
    if spot_change > 0.8:
        return "现货价格跟涨，市场补库意愿有所恢复，需要观察下游订单能否承接。"
    return "期现结构变化温和，供需矛盾暂未显著放大，维持安全库存为主。"


def ensure_report_analysis(db: Session, report: Report | None) -> Report | None:
    if not report:
        return report
    products = db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.display_order).all()
    missing = _missing_analysis(report)
    needs_price_upgrade = _needs_price_action_upgrade(report)
    needs_fundamental_upgrade = _needs_fundamental_upgrade(report)
    needs_macro_upgrade = _needs_macro_upgrade(report)
    needs_policy_upgrade = _needs_policy_upgrade(report)
    needs_conclusion_upgrade = _needs_conclusion_upgrade(report)
    needs_recommendation_upgrade = _needs_recommendation_upgrade(report)
    needs_product_refresh = _needs_product_payload_refresh(report, products)
    if not missing and not needs_price_upgrade and not needs_fundamental_upgrade and not needs_macro_upgrade and not needs_policy_upgrade and not needs_conclusion_upgrade and not needs_recommendation_upgrade and not needs_product_refresh:
        return report
    analysis_sections = _build_analysis_sections(db, products)
    recommendation_text = "\n".join(
        f"{item.product_code}：{item.action}。{item.basis}" for item in report.recommendations
    )
    report.price_behavior_analysis = (
        str(analysis_sections["price_behavior_analysis"])
        if needs_price_upgrade
        else report.price_behavior_analysis or str(analysis_sections["price_behavior_analysis"])
    )
    report.fundamentals_analysis = (
        str(analysis_sections["fundamentals_analysis"])
        if needs_fundamental_upgrade
        else report.fundamentals_analysis
        or recommendation_text
        or str(analysis_sections["fundamentals_analysis"])
        or "暂无可补全的基本面说明。"
    )
    report.macro_analysis = (
        str(analysis_sections["macro_analysis"])
        if needs_macro_upgrade
        else report.macro_analysis
        or str(analysis_sections["macro_analysis"])
        or "宏观面重点跟踪原油、煤化工成本、人民币汇率和工业品风险偏好变化；未形成单边共振前，采购节奏以订单覆盖和现金流安全为主。"
    )
    report.policy_analysis = (
        str(analysis_sections["policy_analysis"])
        if needs_policy_upgrade
        else report.policy_analysis
        or str(analysis_sections["policy_analysis"])
        or "政策面关注能耗、安全生产、环保检查、地产链需求支持政策，以及交易所保证金、限仓和风控规则调整。"
    )
    if needs_price_upgrade or needs_fundamental_upgrade or needs_macro_upgrade or needs_policy_upgrade or needs_conclusion_upgrade or needs_product_refresh or not report.product_analyses:
        report.product_analysis_payload = json.dumps(analysis_sections["product_analyses"], ensure_ascii=False)
    if needs_recommendation_upgrade:
        analysis_map = {item["product_code"]: item for item in analysis_sections["product_analyses"]}
        refreshed_recommendations: list[Recommendation] = []
        for product in products:
            metrics = calculate_metrics(db, product)
            action, basis, risk_note, confidence = build_recommendation(metrics, analysis_map.get(product.code))
            refreshed_recommendations.append(
                Recommendation(
                    product_code=product.code,
                    action=action,
                    basis=basis,
                    risk_note=risk_note,
                    confidence=confidence,
                )
            )
        report.recommendations = refreshed_recommendations
    db.commit()
    db.refresh(report)
    return report


def _signed_pct(value: float | None) -> str:
    if value is None:
        return "-"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


def _signed_value(value: float | None) -> str:
    if value is None:
        return "-"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}"


def latest_public_report(db: Session) -> Report | None:
    report = (
        db.query(Report)
        .filter(Report.status.in_(["published", "pushed"]))
        .order_by(desc(Report.published_at), desc(Report.generated_at))
        .first()
    )
    return ensure_report_analysis(db, report)


def _session_label(session_name: str) -> str:
    return {"morning": "早报", "evening": "晚报", "urgent": "突发快讯"}.get(session_name, "日报")


def _build_analysis_sections(db: Session, products: list[Product]) -> dict[str, object]:
    sync_daily_policy_events(db, products)
    db.flush()
    price_lines: list[str] = []
    fundamental_lines: list[str] = []
    macro_lines: list[str] = []
    policy_lines: list[str] = []
    product_analyses: list[dict[str, str]] = []

    strong_count = 0
    weak_count = 0
    basis_pressure_count = 0
    oi_up_count = 0
    futures_product_count = 0

    for product in products:
        metrics = calculate_metrics(db, product)
        has_futures = metrics.futures_close is not None
        futures_change = metrics.futures_change_pct or 0
        spot_change = metrics.spot_change_pct or 0
        oi_change = metrics.open_interest_change_pct or 0
        basis = metrics.basis_value

        if has_futures:
            futures_product_count += 1
            if futures_change > 0:
                strong_count += 1
            elif futures_change < 0:
                weak_count += 1
            if basis is not None and basis > 0:
                basis_pressure_count += 1
            if oi_change > 0:
                oi_up_count += 1

        price_view = build_price_behavior_view(db, product, metrics)
        fundamental_view = build_fundamental_view(db, product, metrics)
        macro_view = build_macro_view(db, product, metrics)
        policy_view = build_policy_view(db, product, basis)

        price_lines.append(price_view)
        fundamental_lines.append(f"{product.code}：{fundamental_view}")
        analysis_item = {
            "product_code": product.code,
            "price_behavior": price_view,
            "fundamentals": fundamental_view,
            "macro": macro_view,
            "policy": policy_view,
        }
        analysis_item["conclusion"] = build_analysis_conclusion(metrics, analysis_item)
        product_analyses.append(analysis_item)

    product_count = max(futures_product_count, 1)
    strong_threshold = max(3, math.ceil(product_count * 0.55))
    weak_threshold = max(3, math.ceil(product_count * 0.55))
    oi_threshold = max(2, math.ceil(product_count * 0.4))
    macro_bias = (
        "偏强"
        if strong_count >= strong_threshold and oi_up_count >= oi_threshold
        else "偏弱"
        if weak_count >= weak_threshold
        else "震荡"
    )
    macro_lines.append(build_macro_overview(db, product_count, strong_count, weak_count, oi_up_count, macro_bias))

    urgent_policy_count = sum(1 for item in product_analyses if "重大供需事件" in item["policy"])
    if urgent_policy_count:
        policy_lines.append(f"重大供需事件：当前{urgent_policy_count}个品种存在影响供需平衡的突发消息，已在企业微信和客户面政策栏置顶。")
    policy_lines.append("每日政策/产业消息：各品种已按安全生产、环保、检修三类更新，详情见品种政策面。")
    policy_lines.append("政策跟踪：关注能耗、安全生产、环保检查、地产链需求支持政策，以及交易所保证金和限仓调整。")
    if basis_pressure_count >= 2:
        policy_lines.append("当前多个品种现货升水，若保供稳价或仓单流转政策强化，基差可能快速回落。")
    else:
        policy_lines.append("当前基差压力整体可控，政策面更多作为风险提示项，暂不作为追涨采购的核心理由。")
    policy_lines.append("执行建议：遇到政策窗口期或突发监管消息，后台报告需人工复核后再推送客户。")

    return {
        "price_behavior_analysis": "\n".join(price_lines),
        "fundamentals_analysis": "\n".join(fundamental_lines),
        "macro_analysis": "\n".join(macro_lines),
        "policy_analysis": "\n".join(policy_lines),
        "product_analyses": product_analyses,
    }


def _basis_tone(value: float | None) -> str:
    # 与 services/basis.py 同一口径：>10 升水 / <-10 贴水 / 其余平水（正值=现货升水）
    if value is None:
        return "无基差"
    if value > 10:
        return "现货升水"
    if value < -10:
        return "现货贴水"
    return "平水"


def generate_report(db: Session, session_name: str = "evening", force: bool = False) -> Report:
    today = date.today()
    existing = db.query(Report).filter(Report.report_date == today, Report.session_name == session_name).first()
    if existing and existing.status in {"published", "pushed"} and not force:
        return existing

    products = db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.display_order).all()
    analysis_sections = _build_analysis_sections(db, products)
    analysis_map = {item["product_code"]: item for item in analysis_sections["product_analyses"]}
    summary_lines: list[str] = []
    recommendations: list[Recommendation] = []
    for product in products:
        metrics = calculate_metrics(db, product)
        action, basis, risk_note, confidence = build_recommendation(metrics, analysis_map.get(product.code))
        if product.code in analysis_map:
            analysis_map[product.code]["conclusion"] = build_analysis_conclusion(metrics, analysis_map[product.code])
        if metrics.futures_close is None:
            summary_lines.append(
                f"{product.code}：现货{metrics.spot_price or '-'}，纯现货跟踪，无期货基差。"
            )
        else:
            summary_lines.append(
                f"{product.code}：主力合约{metrics.futures_contract or '-'}，期货{metrics.futures_close or '-'}，现货{metrics.spot_price or '-'}，"
                f"基差{metrics.basis_value if metrics.basis_value is not None else '-'}（{_basis_tone(metrics.basis_value)}）。"
            )
        recommendations.append(
            Recommendation(
                product_code=product.code,
                action=action,
                basis=basis,
                risk_note=risk_note,
                confidence=confidence,
            )
        )

    report = existing or Report(report_date=today, session_name=session_name, title="", market_summary="")
    report.title = f"{today:%Y-%m-%d} 多品种期现{_session_label(session_name)}"
    report.market_summary = "\n".join(summary_lines) or "暂无行情数据，请先执行同步或导入现货价格。"
    report.price_behavior_analysis = analysis_sections["price_behavior_analysis"]
    report.fundamentals_analysis = analysis_sections["fundamentals_analysis"]
    report.macro_analysis = analysis_sections["macro_analysis"]
    report.policy_analysis = analysis_sections["policy_analysis"]
    report.product_analysis_payload = json.dumps(analysis_sections["product_analyses"], ensure_ascii=False)
    report.status = "draft"
    report.generated_at = datetime.utcnow()
    report.recommendations = recommendations
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def publish_report(db: Session, report_id: int) -> Report | None:
    report = db.get(Report, report_id)
    if not report:
        return None
    report.status = "published"
    report.published_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report


def mark_report_pushed(db: Session, report: Report) -> None:
    report.status = "pushed"
    report.pushed_at = datetime.utcnow()
    if report.published_at is None:
        report.published_at = report.pushed_at
    db.commit()
    db.refresh(report)
