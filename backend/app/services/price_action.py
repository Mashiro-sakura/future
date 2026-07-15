from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import FuturesPrice, Product
from app.services.analytics import ProductMetrics


@dataclass
class MovingAverageState:
    ma5: float | None
    ma10: float | None
    ma20: float | None
    ma60: float | None
    label: str
    short_bias: str
    middle_bias: str
    long_bias: str


def recent_futures_rows(db: Session, code: str, days: int = 80) -> list[FuturesPrice]:
    rows = (
        db.query(FuturesPrice)
        .filter(FuturesPrice.product_code == code)
        .order_by(desc(FuturesPrice.trade_date))
        .limit(days)
        .all()
    )
    return list(reversed(rows))


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous * 100


def _signed_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{'+' if value > 0 else ''}{value:.2f}%"


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    subset = values[-window:]
    return sum(subset) / window


def _bias_from_pct(value: float | None, threshold: float = 0.35) -> str:
    if value is None or abs(value) < threshold:
        return "震荡"
    return "偏多" if value > 0 else "偏空"


def _moving_average_state(closes: list[float]) -> MovingAverageState:
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    close = closes[-1] if closes else None

    short_bias = _bias_from_pct(_pct(close, ma5))
    middle_bias = _bias_from_pct(_pct(close, ma20 or ma10))
    long_bias = _bias_from_pct(_pct(close, ma60 or ma20 or ma10))

    if close is not None and ma5 and ma10 and ma20 and close > ma5 >= ma10 >= ma20:
        label = "多头排列"
    elif close is not None and ma5 and ma10 and ma20 and close < ma5 <= ma10 <= ma20:
        label = "空头排列"
    elif close is not None and (ma20 or ma10):
        label = "均线纠缠" if abs(_pct(close, ma20 or ma10) or 0) < 0.8 else "均线偏离"
    else:
        label = "均线样本不足"

    return MovingAverageState(ma5, ma10, ma20, ma60, label, short_bias, middle_bias, long_bias)


def _candle_signal(row: FuturesPrice) -> str:
    open_price = row.open_price or row.close_price
    high = row.high_price or row.close_price
    low = row.low_price or row.close_price
    close = row.close_price
    bar_range = max(high - low, 0)
    if bar_range <= 0:
        return "日K线振幅不足，暂按窄幅整理处理"

    body = abs(close - open_price)
    upper_shadow = high - max(open_price, close)
    lower_shadow = min(open_price, close) - low
    close_position = (close - low) / bar_range
    body_ratio = body / bar_range

    if body_ratio >= 0.6 and close > open_price and close_position >= 0.7:
        return "出现收在高位的多头趋势K线"
    if body_ratio >= 0.6 and close < open_price and close_position <= 0.3:
        return "出现收在低位的空头趋势K线"
    if body_ratio <= 0.18:
        return "最新K线为小实体/十字结构，多空短线分歧较大"
    if lower_shadow >= body * 2 and close_position >= 0.55:
        return "下影线明显，低位有承接或试探失败特征"
    if upper_shadow >= body * 2 and close_position <= 0.45:
        return "上影线明显，高位存在抛压或突破失败特征"
    return "最新K线仍属普通震荡结构"


def _swing_points(rows: list[FuturesPrice], kind: str, span: int = 2) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    if len(rows) < span * 2 + 1:
        return points
    for index in range(span, len(rows) - span):
        value = rows[index].high_price if kind == "high" else rows[index].low_price
        if value is None:
            value = rows[index].close_price
        window = rows[index - span : index + span + 1]
        candidates = [
            (item.high_price if kind == "high" else item.low_price) or item.close_price
            for item in window
        ]
        if kind == "high" and value == max(candidates):
            points.append((index, value))
        if kind == "low" and value == min(candidates):
            points.append((index, value))
    return points


def _near(left: float, right: float, tolerance: float = 0.018) -> bool:
    base = max(abs(left), abs(right), 1)
    return abs(left - right) / base <= tolerance


def _pattern_signal(rows: list[FuturesPrice]) -> str:
    if len(rows) < 12:
        return "K线样本偏少，暂不强行识别头肩/W/M结构"

    highs = _swing_points(rows, "high")[-5:]
    lows = _swing_points(rows, "low")[-5:]
    close = rows[-1].close_price

    if len(lows) >= 2:
        first, second = lows[-2], lows[-1]
        if first[0] < second[0] and _near(first[1], second[1], 0.025):
            middle_highs = [value for index, value in highs if first[0] < index < second[0]]
            neckline = max(middle_highs) if middle_highs else None
            if neckline and close >= neckline * 0.985:
                return f"形态上接近W底，两个低点{_fmt(first[1])}/{_fmt(second[1])}接近，价格正在测试颈线{_fmt(neckline)}"
            return f"形态上有W底雏形，但尚未有效站上颈线，确认度一般"

    if len(highs) >= 2:
        first, second = highs[-2], highs[-1]
        if first[0] < second[0] and _near(first[1], second[1], 0.025):
            middle_lows = [value for index, value in lows if first[0] < index < second[0]]
            neckline = min(middle_lows) if middle_lows else None
            if neckline and close <= neckline * 1.015:
                return f"形态上接近M顶，两个高点{_fmt(first[1])}/{_fmt(second[1])}接近，价格正在回测颈线{_fmt(neckline)}"
            return "形态上有M顶雏形，但尚未跌破颈线，仍需等待确认"

    if len(highs) >= 3:
        left, head, right = highs[-3], highs[-2], highs[-1]
        if left[0] < head[0] < right[0] and head[1] > left[1] * 1.01 and head[1] > right[1] * 1.01 and _near(left[1], right[1], 0.035):
            return "形态上有头肩顶迹象，右肩未能突破头部，高位追采购需要谨慎"

    if len(lows) >= 3:
        left, head, right = lows[-3], lows[-2], lows[-1]
        if left[0] < head[0] < right[0] and head[1] < left[1] * 0.99 and head[1] < right[1] * 0.99 and _near(left[1], right[1], 0.035):
            return "形态上有头肩底迹象，右肩不再创新低，若放量站上颈线可提高补库优先级"

    return "暂未识别出清晰头肩顶/头肩底、W底或M顶结构，按趋势线和均线节奏跟踪"


def _range_position(rows: list[FuturesPrice], lookback: int = 20) -> tuple[str, float | None, float | None]:
    subset = rows[-lookback:] if len(rows) >= lookback else rows
    highs = [(row.high_price or row.close_price) for row in subset]
    lows = [(row.low_price or row.close_price) for row in subset]
    if not highs or not lows:
        return "区间位置不明", None, None
    high = max(highs)
    low = min(lows)
    close = rows[-1].close_price
    span = high - low
    if span <= 0:
        return "处于窄幅区间内部", high, low
    position = (close - low) / span
    if position >= 0.78:
        label = "处于近20日区间上沿"
    elif position <= 0.22:
        label = "处于近20日区间下沿"
    else:
        label = "处于近20日区间中部"
    return label, high, low


def _brooks_context(rows: list[FuturesPrice], ma_state: MovingAverageState) -> str:
    if not rows:
        return "Al Brooks语境：样本不足，暂不判断趋势或交易区间"
    candle = _candle_signal(rows[-1])
    closes = [row.close_price for row in rows]
    recent_up = len(closes) >= 3 and closes[-1] > closes[-2] > closes[-3]
    recent_down = len(closes) >= 3 and closes[-1] < closes[-2] < closes[-3]

    if ma_state.middle_bias == "偏多" and ("多头趋势K线" in candle or recent_up):
        return "Al Brooks语境：价格在关键均线上方并有顺势跟进，偏向突破后的回踩买方控盘；若后续没有连续趋势K线，需防范转回交易区间"
    if ma_state.middle_bias == "偏空" and ("空头趋势K线" in candle or recent_down):
        return "Al Brooks语境：价格在关键均线下方并有空头跟进，偏向空方控盘；采购端应等待失败突破或二次进入信号"
    return "Al Brooks语境：当前更接近交易区间环境，单根突破K线的胜率不足，需要等待二次进入、失败突破或连续跟进K线确认"


def _ytc_context(rows: list[FuturesPrice], ma_state: MovingAverageState) -> str:
    position, high, low = _range_position(rows)
    high_low = f"压力{_fmt(high)}、支撑{_fmt(low)}" if high is not None and low is not None else "支撑压力暂不清晰"
    if ma_state.middle_bias == "偏多" and ma_state.short_bias != "偏空":
        return f"YTC语境：高周期偏多，当前{position}，优先观察回踩支撑后的买方反应，{high_low}"
    if ma_state.middle_bias == "偏空" and ma_state.short_bias != "偏多":
        return f"YTC语境：高周期偏空，当前{position}，若反弹无法站回均线，仍按供应压制处理，{high_low}"
    return f"YTC语境：高低周期方向不完全一致，当前{position}，重点看突破失败、假突破和回到价值区后的反应，{high_low}"


def _open_interest_context(metrics: ProductMetrics) -> str:
    futures_change = metrics.futures_change_pct
    oi_change = metrics.open_interest_change_pct
    if futures_change is None or oi_change is None:
        return "持仓量样本不足，暂以价格结构和基差为主"
    if futures_change > 0 and oi_change > 0:
        return f"持仓量配合价格上行，增仓{_signed_pct(oi_change)}，说明新资金偏多参与"
    if futures_change < 0 and oi_change > 0:
        return f"持仓量配合价格下行，增仓{_signed_pct(oi_change)}，说明空头主动性增强"
    if futures_change > 0 and oi_change < 0:
        return f"价格上涨但持仓下降{_signed_pct(oi_change)}，更像空头回补，趋势质量需打折"
    if futures_change < 0 and oi_change < 0:
        return f"价格下跌且持仓下降{_signed_pct(oi_change)}，偏多头离场，杀跌延续性需继续观察"
    return f"持仓变化{_signed_pct(oi_change)}，资金确认度一般"


def _multi_timeframe_context(closes: list[float], ma_state: MovingAverageState) -> str:
    short_pct = _pct(closes[-1], closes[-4]) if len(closes) >= 4 else None
    middle_pct = _pct(closes[-1], closes[-11]) if len(closes) >= 11 else None
    long_pct = _pct(closes[-1], closes[-31]) if len(closes) >= 31 else None
    biases = [_bias_from_pct(short_pct), _bias_from_pct(middle_pct), _bias_from_pct(long_pct)]

    if all(item == "偏多" for item in biases if item != "震荡") and "偏空" not in biases:
        resonance = "多周期共振偏多"
    elif all(item == "偏空" for item in biases if item != "震荡") and "偏多" not in biases:
        resonance = "多周期共振偏空"
    else:
        resonance = "多周期信号分歧"

    return (
        f"{resonance}；短周期{biases[0]}、中周期{biases[1]}、长周期{biases[2]}，"
        f"均线状态为{ma_state.label}"
    )


def _procurement_read(metrics: ProductMetrics, ma_state: MovingAverageState) -> str:
    basis_pct = None
    if metrics.basis_value is not None and metrics.futures_close:
        basis_pct = metrics.basis_value / metrics.futures_close * 100
    if ma_state.middle_bias == "偏多" and basis_pct is not None and basis_pct < 0:
        return "采购含义：盘面偏多且现货贴水，刚需可优先小单锁价，但仍要用止损/套保控制回撤"
    if ma_state.middle_bias == "偏多" and basis_pct is not None and basis_pct > 1.2:
        return "采购含义：盘面偏多但现货升水较高，适合分批补库，不宜一次性追高"
    if ma_state.middle_bias == "偏空":
        return "采购含义：盘面结构偏空，现货采购以刚需为主，等待均线收复或形态失败后再提高补库比例"
    return "采购含义：趋势确认度一般，按安全库存和订单覆盖执行，等待基差或形态给出更明确窗口"


def build_price_behavior_view(db: Session, product: Product, metrics: ProductMetrics, days: int = 80) -> str:
    if not (product.futures_symbol or "").strip() or product.exchange == "SPOT" or metrics.futures_close is None:
        return (
            f"{product.code}（{product.name}）为现货品种，暂不做期货盘面分析。"
            f"价格行为以华东现货{_fmt(metrics.spot_price)}、现货变动{_signed_pct(metrics.spot_change_pct)}、"
            "华东/华南/西南区域报价、库存、开工率和产业链成本传导为主；"
            "短线重点观察现货报价是否连续上移或下移、区域价差是否扩大，以及成交放量后能否被下游订单承接。"
        )

    rows = recent_futures_rows(db, product.code, days=days)
    if not rows:
        return (
            f"{product.code}主力合约{metrics.futures_contract or '-'}：期货{_fmt(metrics.futures_close)}，"
            f"现货{_fmt(metrics.spot_price)}，基差{_fmt(metrics.basis_value)}。行情样本不足，暂不能识别K线形态、均线和多周期共振。"
        )

    closes = [row.close_price for row in rows]
    ma_state = _moving_average_state(closes)
    pattern = _pattern_signal(rows)
    candle = _candle_signal(rows[-1])
    brooks = _brooks_context(rows, ma_state)
    ytc = _ytc_context(rows, ma_state)
    oi = _open_interest_context(metrics)
    multi_timeframe = _multi_timeframe_context(closes, ma_state)
    procurement = _procurement_read(metrics, ma_state)

    ma_text = (
        f"MA5={_fmt(ma_state.ma5)}，MA10={_fmt(ma_state.ma10)}，"
        f"MA20={_fmt(ma_state.ma20)}，MA60={_fmt(ma_state.ma60)}"
    )
    contract = metrics.futures_contract or rows[-1].contract_code or "-"
    return (
        f"{product.code}主力合约{contract}：期货{_fmt(metrics.futures_close)}，现货{_fmt(metrics.spot_price)}，"
        f"基差{_fmt(metrics.basis_value)}；期货变动{_signed_pct(metrics.futures_change_pct)}，"
        f"现货变动{_signed_pct(metrics.spot_change_pct)}，持仓变动{_signed_pct(metrics.open_interest_change_pct)}。\n"
        f"K线/形态：{candle}；{pattern}。\n"
        f"均线/多周期：{ma_text}，{multi_timeframe}。\n"
        f"持仓量：{oi}。\n"
        f"{brooks}。\n"
        f"{ytc}。\n"
        f"{procurement}。"
    )
