from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import InventorySnapshot, OperatingRateSnapshot, Product, SpotPrice
from app.services.analytics import ProductMetrics


SPOT_REGIONS = ("华东", "华南", "西南")


@dataclass
class InventoryState:
    latest_social: float | None
    latest_factory: float | None
    latest_total: float | None
    social_change_5d: float | None
    factory_change_5d: float | None
    total_change_5d: float | None
    total_change_20d: float | None
    unit: str


@dataclass
class OperatingRateState:
    latest_rate: float | None
    change_5d: float | None
    change_20d: float | None
    unit: str


def recent_inventory_rows(db: Session, code: str, days: int = 60) -> list[InventorySnapshot]:
    rows = (
        db.query(InventorySnapshot)
        .filter(InventorySnapshot.product_code == code)
        .order_by(desc(InventorySnapshot.trade_date))
        .limit(days)
        .all()
    )
    return list(reversed(rows))


def latest_regional_spot_quotes(db: Session, code: str) -> dict[str, SpotPrice]:
    quotes: dict[str, SpotPrice] = {}
    for region in SPOT_REGIONS:
        row = (
            db.query(SpotPrice)
            .filter(SpotPrice.product_code == code, SpotPrice.region == region)
            .order_by(desc(SpotPrice.trade_date))
            .first()
        )
        if row:
            quotes[region] = row
    return quotes


def recent_operating_rate_rows(db: Session, code: str, days: int = 60) -> list[OperatingRateSnapshot]:
    rows = (
        db.query(OperatingRateSnapshot)
        .filter(OperatingRateSnapshot.product_code == code)
        .order_by(desc(OperatingRateSnapshot.trade_date))
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


def _total(row: InventorySnapshot | None) -> float | None:
    if row is None:
        return None
    social = row.social_inventory or 0
    factory = row.factory_inventory or 0
    if row.social_inventory is None and row.factory_inventory is None:
        return None
    return social + factory


def _inventory_state(rows: list[InventorySnapshot]) -> InventoryState:
    latest = rows[-1] if rows else None
    previous_5d = rows[-6] if len(rows) >= 6 else (rows[0] if len(rows) >= 2 else None)
    previous_20d = rows[-21] if len(rows) >= 21 else (rows[0] if len(rows) >= 2 else None)
    return InventoryState(
        latest_social=latest.social_inventory if latest else None,
        latest_factory=latest.factory_inventory if latest else None,
        latest_total=_total(latest),
        social_change_5d=_pct(latest.social_inventory if latest else None, previous_5d.social_inventory if previous_5d else None),
        factory_change_5d=_pct(latest.factory_inventory if latest else None, previous_5d.factory_inventory if previous_5d else None),
        total_change_5d=_pct(_total(latest), _total(previous_5d)),
        total_change_20d=_pct(_total(latest), _total(previous_20d)),
        unit=latest.inventory_unit if latest else "万吨",
    )


def _operating_rate_state(rows: list[OperatingRateSnapshot]) -> OperatingRateState:
    latest = rows[-1] if rows else None
    previous_5d = rows[-6] if len(rows) >= 6 else (rows[0] if len(rows) >= 2 else None)
    previous_20d = rows[-21] if len(rows) >= 21 else (rows[0] if len(rows) >= 2 else None)
    return OperatingRateState(
        latest_rate=latest.operating_rate if latest else None,
        change_5d=_pct(latest.operating_rate if latest else None, previous_5d.operating_rate if previous_5d else None),
        change_20d=_pct(latest.operating_rate if latest else None, previous_20d.operating_rate if previous_20d else None),
        unit=latest.unit if latest else "%",
    )


def _inventory_cycle(price_change: float, inventory_change: float | None) -> str:
    if inventory_change is None:
        return "库存周期样本不足"
    if price_change >= 0 and inventory_change >= 0:
        return "主动补库存"
    if price_change >= 0 and inventory_change < 0:
        return "被动去库存"
    if price_change < 0 and inventory_change < 0:
        return "主动去库存"
    return "被动补库存"


def _cycle_explanation(cycle: str) -> str:
    return {
        "主动补库存": "价格走强且库存回升，说明产业链补库意愿增强，但若后续需求兑现不足，容易转成库存压力。",
        "被动去库存": "价格走强但库存下降，说明需求消化快于供应投放，供需偏紧信号更强。",
        "主动去库存": "价格走弱且库存下降，说明产业链在压缩库存，采购宜保持刚需节奏。",
        "被动补库存": "价格走弱但库存回升，说明需求承接不足或供应压力偏大，是供需失衡的主要警戒区。",
    }.get(cycle, "库存样本不足，暂不能确认库存周期。")


def _imbalance_label(metrics: ProductMetrics, state: InventoryState, operating_state: OperatingRateState) -> str:
    basis_pct = metrics.basis_value / metrics.futures_close * 100 if metrics.basis_value is not None and metrics.futures_close else 0
    total_change = state.total_change_5d or 0
    social_change = state.social_change_5d or 0
    factory_change = state.factory_change_5d or 0
    spot_change = metrics.spot_change_pct or 0
    operating_change = operating_state.change_5d or 0

    if total_change > 2.5 and operating_change > 1.5 and spot_change <= 0 and basis_pct <= 0.6:
        return "供给扩张叠加库存累积，需求承接不足"
    if total_change > 2.5 and spot_change <= 0 and basis_pct <= 0.6:
        return "供给过剩/需求承接不足"
    if total_change < -2.0 and operating_change < -1.0 and (basis_pct >= 0.8 or spot_change > 0):
        return "降负去库，供需偏紧"
    if total_change < -2.0 and (basis_pct >= 0.8 or spot_change > 0):
        return "供需偏紧/去库较快"
    if operating_change > 2.0 and total_change <= 0:
        return "开工提升但库存未累，需求消化尚可"
    if operating_change < -2.0 and total_change >= 0:
        return "开工回落但库存未降，需求偏弱"
    if factory_change > 3.0 and social_change <= 0:
        return "工厂库存压力上升，渠道消化一般"
    if social_change > 3.0 and factory_change <= 0:
        return "社会库存累积，贸易环节承接压力增加"
    return "供需大体平衡，暂未出现明显失衡"


def _procurement_view(cycle: str, imbalance: str, metrics: ProductMetrics) -> str:
    if "供需偏紧" in imbalance or "降负去库" in imbalance:
        return "采购含义：若订单刚需明确，可采取小单滚动补库；高升水阶段避免一次性追高。"
    if "供给过剩" in imbalance or "供给扩张" in imbalance or cycle == "被动补库存":
        return "采购含义：库存压力偏大，优先消耗自有库存，等待现货让利、基差回落或主动去库后再提高采购比例。"
    if cycle == "主动去库存":
        return "采购含义：产业链仍在压库存，建议维持安全库存，不急于扩大采购敞口。"
    if cycle == "主动补库存":
        return "采购含义：补库意愿有恢复，可结合订单覆盖分批锁定，不宜脱离现金流安全。"
    if metrics.basis_value is not None and metrics.basis_value < 0:
        return "采购含义：现货贴水提供一定采购窗口，可按刚需分批锁价。"
    return "采购含义：供需信号尚未单边化，维持安全库存和订单覆盖优先。"


def _regional_spot_text(quotes: dict[str, SpotPrice], metrics: ProductMetrics) -> str:
    if not quotes:
        return "区域现货：华东、华南、西南报价暂缺，需通过后台同步或CSV导入补充。"

    date_text = max(row.trade_date for row in quotes.values()).isoformat()
    quote_parts: list[str] = []
    for region in SPOT_REGIONS:
        row = quotes.get(region)
        if row:
            quote_parts.append(f"{region}{_fmt(row.price)}")
        elif region == "华东" and metrics.spot_price is not None:
            quote_parts.append(f"{region}{_fmt(metrics.spot_price)}")
        else:
            quote_parts.append(f"{region}-")

    east = quotes.get("华东")
    south = quotes.get("华南")
    southwest = quotes.get("西南")
    spread_parts: list[str] = []
    if east and south:
        spread_parts.append(f"华南-华东{_fmt(south.price - east.price)}")
    if east and southwest:
        spread_parts.append(f"西南-华东{_fmt(southwest.price - east.price)}")
    spread_text = "；区域价差：" + "，".join(spread_parts) if spread_parts else ""
    return f"区域现货（{date_text}）：{'，'.join(quote_parts)}{spread_text}。"


def build_fundamental_view(db: Session, product: Product, metrics: ProductMetrics) -> str:
    rows = recent_inventory_rows(db, product.code, days=60)
    regional_quotes = latest_regional_spot_quotes(db, product.code)
    operating_rows = recent_operating_rate_rows(db, product.code, days=60)
    state = _inventory_state(rows)
    operating_state = _operating_rate_state(operating_rows)
    price_change = metrics.spot_change_pct if metrics.spot_change_pct is not None else metrics.futures_change_pct or 0
    cycle = _inventory_cycle(price_change, state.total_change_5d)
    imbalance = _imbalance_label(metrics, state, operating_state)
    basis_text = _fmt(metrics.basis_value)
    pricing_reference = (
        f"现货/期货基差{basis_text}"
        if metrics.futures_close is not None
        else "华东/华南/西南现货报价、开工率"
    )
    unit = state.unit

    inventory_text = (
        f"{_regional_spot_text(regional_quotes, metrics)}"
        f"开工率{_fmt(operating_state.latest_rate)}{operating_state.unit}，5日变化{_signed_pct(operating_state.change_5d)}，20日变化{_signed_pct(operating_state.change_20d)}；"
        f"社会库存{_fmt(state.latest_social)}{unit}，5日变化{_signed_pct(state.social_change_5d)}；"
        f"工厂库存{_fmt(state.latest_factory)}{unit}，5日变化{_signed_pct(state.factory_change_5d)}；"
        f"总库存{_fmt(state.latest_total)}{unit}，5日变化{_signed_pct(state.total_change_5d)}，20日变化{_signed_pct(state.total_change_20d)}。"
    )
    cycle_text = f"库存周期：当前处于{cycle}阶段，{_cycle_explanation(cycle)}"
    supply_demand_text = f"供需判断：{imbalance}；结合{pricing_reference}和价格变化，观察库存是否继续累积或去化。"
    return f"{inventory_text}{cycle_text}{supply_demand_text}{_procurement_view(cycle, imbalance, metrics)}"
