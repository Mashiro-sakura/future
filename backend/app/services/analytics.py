from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import FuturesPrice, Product, Recommendation, Report, SpotPrice


RECOMMENDATION_ACTIONS = ["积极采购", "小单补库", "观望等待", "逢低采购", "套保关注"]
BENCHMARK_SPOT_REGION = "华东"


@dataclass
class ProductMetrics:
    product_code: str
    futures_contract: str | None
    futures_close: float | None
    spot_price: float | None
    basis_value: float | None
    futures_change_pct: float | None
    spot_change_pct: float | None
    open_interest_change_pct: float | None


@dataclass
class DimensionScore:
    score: int
    reason: str


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _clip(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 2)


def _comparable_sources(current: FuturesPrice | None, previous: FuturesPrice | None) -> bool:
    if not current or not previous:
        return False
    return not ("fallback-demo" in {current.source, previous.source} and current.source != previous.source)


def latest_two_futures(db: Session, code: str) -> list[FuturesPrice]:
    return (
        db.query(FuturesPrice)
        .filter(FuturesPrice.product_code == code)
        .order_by(desc(FuturesPrice.trade_date))
        .limit(2)
        .all()
    )


def latest_two_spot(db: Session, code: str, region: str = BENCHMARK_SPOT_REGION) -> list[SpotPrice]:
    return (
        db.query(SpotPrice)
        .filter(SpotPrice.product_code == code)
        .filter(SpotPrice.region == region)
        .order_by(desc(SpotPrice.trade_date))
        .limit(2)
        .all()
    )


def calculate_metrics(db: Session, product: Product) -> ProductMetrics:
    futures_rows = latest_two_futures(db, product.code)
    spot_rows = latest_two_spot(db, product.code)
    current_futures = futures_rows[0] if futures_rows else None
    previous_futures = futures_rows[1] if len(futures_rows) > 1 else None
    current_spot = spot_rows[0] if spot_rows else None
    previous_spot = spot_rows[1] if len(spot_rows) > 1 else None

    futures_close = current_futures.close_price if current_futures else None
    spot_price = current_spot.price if current_spot else None
    basis = round(spot_price - futures_close, 2) if spot_price is not None and futures_close is not None else None
    futures_rows_are_comparable = _comparable_sources(current_futures, previous_futures)

    return ProductMetrics(
        product_code=product.code,
        futures_contract=current_futures.contract_code if current_futures and current_futures.contract_code else None,
        futures_close=futures_close,
        spot_price=spot_price,
        basis_value=basis,
        futures_change_pct=_pct(futures_close, previous_futures.close_price if futures_rows_are_comparable else None),
        spot_change_pct=_pct(spot_price, previous_spot.price if previous_spot else None),
        open_interest_change_pct=_pct(
            current_futures.open_interest if current_futures else None,
            previous_futures.open_interest if futures_rows_are_comparable else None,
        ),
    )


def _score_price_dimension(metrics: ProductMetrics, text: str) -> DimensionScore:
    futures_change = metrics.futures_change_pct or 0
    spot_change = metrics.spot_change_pct or 0
    oi_change = metrics.open_interest_change_pct or 0
    basis = metrics.basis_value
    basis_pct = basis / metrics.futures_close * 100 if basis is not None and metrics.futures_close else 0
    score = 0
    reasons: list[str] = []

    if metrics.futures_close is None:
        if spot_change < -0.8:
            score += 2
            reasons.append(f"现货下跌{abs(spot_change):.2f}%，低价采购窗口打开")
        elif spot_change > 0.8:
            score += 1
            reasons.append(f"现货上涨{spot_change:.2f}%，刚需补库需防被动追价")
        else:
            reasons.append(f"现货变化{spot_change:.2f}%，价格驱动偏中性")
    else:
        if basis_pct <= -1.2:
            score += 3
            reasons.append(f"现货较期货贴水约{abs(basis_pct):.2f}%，采购成本有优势")
        elif basis_pct >= 1.2:
            score -= 2
            reasons.append(f"现货较期货升水约{basis_pct:.2f}%，高价库存风险上升")
        if spot_change < -0.8:
            score += 1
            reasons.append(f"现货下跌{abs(spot_change):.2f}%，可等待成交确认后分批锁价")
        elif spot_change > 0.8 and basis_pct >= 0:
            score -= 1
            reasons.append(f"现货上涨{spot_change:.2f}%且缺少贴水保护")
        if futures_change > 1.0 and oi_change > 1.5:
            score += 1
            reasons.append(f"期货上涨{futures_change:.2f}%且持仓增加{oi_change:.2f}%，资金推动偏强")
        elif futures_change < -1.0 and oi_change > 1.5:
            score -= 2
            reasons.append(f"期货下跌{abs(futures_change):.2f}%且增仓，空头主动性偏强")

    bullish_signal = _contains_any(text, ("W底", "头肩底", "多头排列", "多周期共振偏多", "买方控盘"))
    bearish_signal = _contains_any(text, ("M顶", "头肩顶", "空头排列", "多周期共振偏空", "空方控盘"))
    if bullish_signal and bearish_signal:
        reasons.append("价格行为多空信号分歧，需等待形态和均线进一步确认")
    elif bullish_signal:
        score += 1
        reasons.append("K线形态、均线或多周期信号偏多")
    elif bearish_signal:
        score -= 1
        reasons.append("K线形态、均线或多周期信号偏空")
    if abs(futures_change) >= 2.0 or abs(oi_change) >= 8.0:
        reasons.append("盘面波动或持仓扰动较大，需纳入套保评估")
    return DimensionScore(_clip(score, -4, 4), "；".join(reasons[:4]) or "价格行为信号暂不明确")


def _score_fundamental_dimension(text: str) -> DimensionScore:
    score = 0
    reasons: list[str] = []
    if _contains_any(text, ("供需偏紧", "降负去库", "被动去库存", "库存下降", "库存去化", "需求消化快于供应")):
        score += 3
        reasons.append("供需偏紧或库存去化，安全库存需要优先保证")
    if _contains_any(text, ("供给过剩", "供给扩张", "库存累积", "被动补库存", "需求承接不足", "库存压力偏大")):
        score -= 3
        reasons.append("库存累积或需求承接不足，扩大采购需谨慎")
    if _contains_any(text, ("开工提升但库存未累", "需求消化尚可")):
        score += 1
        reasons.append("开工提升但库存未累，需求承接尚可")
    if _contains_any(text, ("开工回落但库存未降", "工厂库存压力上升", "社会库存累积")):
        score -= 1
        reasons.append("开工、社会库存或工厂库存结构显示供需仍有压力")
    return DimensionScore(_clip(score, -4, 4), "；".join(reasons) or "基本面暂未给出单边供需信号")


def _score_macro_dimension(text: str) -> DimensionScore:
    score = 0
    reasons: list[str] = []
    if _contains_any(text, ("人民币走弱", "进口成本", "成本支撑", "原油走强", "处于扩张区间")):
        score += 1
        reasons.append("汇率、原油或经济信号对成本/需求有支撑")
    if _contains_any(text, ("人民币走强", "进口成本压力缓和", "原油回落", "处于收缩区间", "风险偏好回落")):
        score -= 1
        reasons.append("宏观成本或需求预期降温")
    if text.count("扩张区间") >= 2:
        score += 1
        reasons.append("中美制造业指标同步偏扩张")
    return DimensionScore(_clip(score, -3, 3), "；".join(reasons[:3]) or "宏观面暂按中性处理")


def _score_policy_dimension(text: str) -> DimensionScore:
    score = 0
    reasons: list[str] = []
    has_major = _contains_any(text, ("重大供需事件", "供需突发", "重大关注"))
    if has_major and _contains_any(text, ("临停", "停车", "限产", "供应收缩", "检查趋严", "重启延后", "物流受阻")):
        score += 3
        reasons.append("重大政策/产业事件可能压缩供应，需提高采购响应速度")
    elif has_major and _contains_any(text, ("需求回落", "供应释放", "重启增加", "库存累积", "供应增加")):
        score -= 3
        reasons.append("重大政策/产业事件偏向供应释放或需求转弱")
    elif has_major:
        reasons.append("存在重大供需事件，需优先人工复核影响范围")
    if _contains_any(text, ("安全检查", "环保检查", "计划检修", "临停", "降负")):
        score += 1
        reasons.append("安全、环保或检修消息可能影响供应弹性")
    if _contains_any(text, ("重启", "供应释放", "库存累积")):
        score -= 1
        reasons.append("装置重启或库存累积会削弱采购窗口")
    return DimensionScore(_clip(score, -4, 4), "；".join(reasons[:3]) or "政策面暂无重大供需扰动")


def _dimension_scores(metrics: ProductMetrics, analysis: dict[str, str] | None) -> dict[str, DimensionScore]:
    analysis = analysis or {}
    return {
        "price": _score_price_dimension(metrics, analysis.get("price_behavior", "")),
        "fundamental": _score_fundamental_dimension(analysis.get("fundamentals", "")),
        "macro": _score_macro_dimension(analysis.get("macro", "")),
        "policy": _score_policy_dimension(analysis.get("policy", "")),
    }


def _action_from_scores(metrics: ProductMetrics, scores: dict[str, DimensionScore]) -> str:
    total = sum(item.score for item in scores.values())
    basis_pct = metrics.basis_value / metrics.futures_close * 100 if metrics.basis_value is not None and metrics.futures_close else 0
    futures_change = metrics.futures_change_pct or 0
    oi_change = metrics.open_interest_change_pct or 0
    hedge_flag = abs(futures_change) >= 2.0 or abs(oi_change) >= 8.0 or abs(scores["policy"].score) >= 3
    cheap_window = metrics.futures_close is None and (metrics.spot_change_pct or 0) < -0.8
    cheap_window = cheap_window or (metrics.futures_close is not None and (basis_pct <= -0.8 or (metrics.spot_change_pct or 0) < -0.8))

    if hedge_flag and -2 <= total <= 3:
        return "套保关注"
    if total >= 6 and basis_pct < 1.8:
        return "积极采购"
    if total >= 3:
        return "小单补库"
    if total >= 1 and cheap_window:
        return "逢低采购"
    return "观望等待"


def _confidence_from_scores(action: str, scores: dict[str, DimensionScore]) -> int:
    values = [item.score for item in scores.values()]
    total = sum(values)
    positive = sum(1 for value in values if value > 0)
    negative = sum(1 for value in values if value < 0)
    confidence = 62 + min(abs(total) * 4, 20)
    if positive >= 3 or negative >= 3:
        confidence += 8
    if positive >= 2 and negative >= 2:
        confidence -= 10
    if action == "观望等待" and positive >= 1 and negative >= 1:
        confidence += 4
    return _clip(confidence, 58, 90)


def build_analysis_conclusion(metrics: ProductMetrics, analysis: dict[str, str] | None = None) -> str:
    scores = _dimension_scores(metrics, analysis)
    action = _action_from_scores(metrics, scores)
    total = sum(item.score for item in scores.values())
    return (
        f"结论：四维综合评分{total}，价格行为{scores['price'].score}分、基本面{scores['fundamental'].score}分、"
        f"宏观面{scores['macro'].score}分、政策面{scores['policy'].score}分；综合判断建议{action}。"
    )


def build_recommendation(metrics: ProductMetrics, analysis: dict[str, str] | None = None) -> tuple[str, str, str, int]:
    scores = _dimension_scores(metrics, analysis)
    action = _action_from_scores(metrics, scores)
    confidence = _confidence_from_scores(action, scores)
    total = sum(item.score for item in scores.values())
    basis_text = (
        f"四维综合评分{total}：价格行为（{scores['price'].reason}）；"
        f"基本面（{scores['fundamental'].reason}）；"
        f"宏观面（{scores['macro'].reason}）；"
        f"政策面（{scores['policy'].reason}）。据此建议{action}。"
    )
    risk_parts = []
    if scores["price"].score < 0:
        risk_parts.append("盘面或价格行为偏弱时，不宜脱离成交确认追采购")
    if scores["fundamental"].score < 0:
        risk_parts.append("供需或库存端仍有压力，需防范低价后继续让利")
    if scores["macro"].score < 0:
        risk_parts.append("宏观成本/需求预期转弱可能压低估值")
    if abs(scores["policy"].score) >= 3:
        risk_parts.append("重大政策/产业事件需人工复核影响范围，必要时同步套保")
    if not risk_parts:
        risk_parts.append("关注现货报价样本偏差、装置开工、库存和下游订单变化")
    risk = "风险提示：" + "；".join(risk_parts[:3]) + "。"
    return action, basis_text, risk, confidence


def trend_points(db: Session, code: str, days: int = 60) -> list[dict[str, object]]:
    futures_rows = (
        db.query(FuturesPrice)
        .filter(FuturesPrice.product_code == code)
        .order_by(desc(FuturesPrice.trade_date))
        .limit(days)
        .all()
    )
    spot_rows = (
        db.query(SpotPrice)
        .filter(SpotPrice.product_code == code, SpotPrice.region == BENCHMARK_SPOT_REGION)
        .order_by(desc(SpotPrice.trade_date))
        .limit(days)
        .all()
    )
    by_date: dict[date, dict[str, object]] = {}
    for row in futures_rows:
        by_date.setdefault(row.trade_date, {"trade_date": row.trade_date})
        by_date[row.trade_date].update(
            {
                "futures_contract": row.contract_code or None,
                "futures_close": row.close_price,
                "open_interest": row.open_interest,
                "volume": row.volume,
            }
        )
    for row in spot_rows:
        by_date.setdefault(row.trade_date, {"trade_date": row.trade_date})
        by_date[row.trade_date]["spot_price"] = row.price
    return [by_date[item] for item in sorted(by_date.keys())]


def overview_products(db: Session, latest_report: Report | None = None) -> list[dict[str, object]]:
    products = db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.display_order).all()
    recommendations: dict[str, Recommendation] = {}
    if latest_report:
        recommendations = {item.product_code: item for item in latest_report.recommendations}

    rows: list[dict[str, object]] = []
    for product in products:
        metrics = calculate_metrics(db, product)
        recommendation = recommendations.get(product.code)
        rows.append(
            {
                "code": product.code,
                "name": product.name,
                "futures_contract": metrics.futures_contract,
                "futures_close": metrics.futures_close,
                "spot_price": metrics.spot_price,
                "basis_value": metrics.basis_value,
                "futures_change_pct": metrics.futures_change_pct,
                "spot_change_pct": metrics.spot_change_pct,
                "open_interest_change_pct": metrics.open_interest_change_pct,
                "recommendation": recommendation.action if recommendation else None,
                "confidence": recommendation.confidence if recommendation else None,
            }
        )
    return rows
