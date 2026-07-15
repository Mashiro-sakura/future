from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import MacroSnapshot, Product
from app.services.analytics import ProductMetrics


MACRO_INDICATORS = ("USD_CNY", "BRENT", "CHINA_PMI", "US_PMI")


def latest_macro_snapshots(db: Session) -> dict[str, MacroSnapshot]:
    rows: dict[str, MacroSnapshot] = {}
    for code in MACRO_INDICATORS:
        row = (
            db.query(MacroSnapshot)
            .filter(MacroSnapshot.indicator_code == code)
            .order_by(desc(MacroSnapshot.trade_date))
            .first()
        )
        if row:
            rows[code] = row
    return rows


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _signed_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{'+' if value > 0 else ''}{value:.2f}%"


def _direction(change_pct: float | None, up: str, down: str, flat: str = "平稳") -> str:
    if change_pct is None or abs(change_pct) < 0.15:
        return flat
    return up if change_pct > 0 else down


def _row_text(row: MacroSnapshot | None) -> str:
    if not row:
        return "暂无"
    unit = row.unit or ""
    return f"{_fmt(row.value)}{unit}，日变化{_signed_pct(row.change_pct)}"


def _fx_view(row: MacroSnapshot | None) -> str:
    if not row:
        return "美元兑人民币暂无最新快照，汇率影响暂按中性处理。"
    direction = _direction(row.change_pct, "人民币走弱", "人民币走强")
    if row.change_pct and row.change_pct > 0:
        effect = "进口成本和以美元计价原料压力上升，对油化工、油脂和有色链条偏成本支撑。"
    elif row.change_pct and row.change_pct < 0:
        effect = "进口成本压力缓和，对进口依赖度高的原料端形成一定降温。"
    else:
        effect = "汇率扰动不强，更多作为成本和风险偏好的背景变量。"
    return f"美元兑人民币{_row_text(row)}，{direction}；{effect}"


def _economy_view(china: MacroSnapshot | None, us: MacroSnapshot | None, product: Product) -> str:
    china_state = "扩张" if china and china.value >= 50 else "收缩" if china else "不明"
    us_state = "扩张" if us and us.value >= 50 else "收缩" if us else "不明"
    product_hint = {
        "CU": "铜对中国基建、制造业、家电和电网订单最敏感，美国制造业影响外需和全球风险偏好。",
        "PB": "铅对汽车、电池和再生铅链条更敏感，中国终端订单决定现货承接，美国周期影响有色估值。",
        "P": "棕榈油受中国油脂消费、进口利润、美国豆油和生柴预期共同影响。",
        "PVC": "PVC更依赖中国地产、基建和建材需求，美国经济主要通过外需与商品风险偏好传导。",
        "PTA": "PTA受中国聚酯、纺织服装订单和出口链条影响，美国消费周期会影响终端纺服外需。",
        "PX": "PX受中国芳烃、PTA开工和亚洲调油需求影响，美国经济通过原油和成品油需求传导。",
        "LLDPE": "LLDPE受包装、农膜、进口窗口和中国消费需求影响，美国周期主要影响全球聚烯烃贸易流。",
        "PP": "PP受家电、汽车、包装和拉丝需求影响，中国制造业订单是主要驱动，美国周期影响出口与风险偏好。",
        "PL": "丙烯受炼厂、PDH、聚丙烯和化工下游开工影响，中美制造业周期会影响化工品订单弹性。",
        "OCT": "辛醇受中国增塑剂、DOP/DOTP、涂料和溶剂需求影响，美国经济通过化工品外需和全球风险偏好传导。",
    }.get(product.code, "该品种受中国工业需求和美国经济风险偏好共同影响。")
    return (
        f"中国经济：制造业PMI{_row_text(china)}，处于{china_state}区间；"
        f"美国经济：制造业PMI{_row_text(us)}，处于{us_state}区间。{product_hint}"
    )


def _crude_view(row: MacroSnapshot | None, product: Product) -> str:
    if not row:
        return "原油暂无最新快照，暂按成本端中性处理。"
    crude_direction = _direction(row.change_pct, "原油走强", "原油回落")
    sensitivity = {
        "PTA": "PTA通过原油-石脑油-PX-PTA链条传导，原油上行会抬升芳烃估值和成本中枢。",
        "PX": "PX处在芳烃链条核心位置，原油和石脑油变化会直接影响PX加工利润和估值。",
        "LLDPE": "LLDPE受原油、石脑油、乙烯和进口窗口影响，油价上行通常抬高成本支撑。",
        "PP": "PP受原油、丙烷、甲醇和丙烯多路线成本影响，油价变化会改变不同工艺利润。",
        "PL": "丙烯受原油、丙烷、炼厂开工和PDH利润影响，油价变化会改变供给端弹性。",
        "PVC": "PVC直接油价弹性低于聚烯烃，但煤化工、电石和乙烯法成本会受能源价格间接影响。",
        "P": "棕榈油受原油和生物柴油价差影响，原油走强会增强生柴掺混和油脂估值支撑。",
        "CU": "铜对原油直接成本弹性有限，但油价影响通胀预期、美元利率预期和大宗商品风险偏好。",
        "PB": "铅对原油直接弹性有限，主要通过运输、冶炼成本和有色板块风险偏好传导。",
        "OCT": "辛醇受丙烯、合成气和丁辛醇装置成本影响，原油上行会抬升化工品成本中枢与风险偏好。",
    }.get(product.code, "原油主要通过能源成本和风险偏好影响该品种。")
    return f"原油：布伦特{_row_text(row)}，{crude_direction}；{sensitivity}"


def _chain_view(product: Product, metrics: ProductMetrics) -> str:
    basis_hint = ""
    if metrics.basis_value is not None and metrics.basis_value > 80:
        basis_hint = "当前现货升水偏高，说明产业链局部流通或交付弹性偏紧，宏观利多会更容易放大现货采购压力。"
    elif metrics.basis_value is not None and metrics.basis_value < -80:
        basis_hint = "当前现货贴水偏深，说明下游承接不足或供应释放偏快，宏观利多需要先观察现货成交修复。"
    else:
        basis_hint = "当前基差压力相对可控，产业链信号需要结合订单和库存继续确认。"

    chain = {
        "PTA": "产业链传导：原油/石脑油 -> PX -> PTA -> 聚酯 -> 织造服装。关注PX加工费、PTA装置检修、聚酯开工和终端纺服订单。",
        "PX": "产业链传导：原油/石脑油 -> 重整/芳烃 -> PX -> PTA。关注调油需求、PX装置负荷和PTA开工对PX去库的拉动。",
        "PVC": "产业链传导：煤炭/电石/乙烯 -> PVC -> 管材/型材/地产基建。关注地产施工、基建订单、氯碱综合利润和社会库存。",
        "LLDPE": "产业链传导：原油/石脑油/乙烷 -> 乙烯 -> LLDPE -> 包装/农膜。关注进口窗口、农膜季节性和下游订单。",
        "PP": "产业链传导：原油/丙烷/甲醇 -> 丙烯 -> PP -> 拉丝/注塑/纤维。关注PDH利润、煤化工利润和终端开工。",
        "PL": "产业链传导：炼厂/PDH -> 丙烯 -> PP/环氧丙烷/丙烯腈。关注炼厂开工、PDH利润和下游化工开工。",
        "P": "产业链传导：东南亚产量/出口 -> 国内进口到港 -> 油脂消费/生柴 -> 棕榈油价格。关注马棕出口、库存和豆棕价差。",
        "CU": "产业链传导：铜矿 -> 冶炼 -> 精铜/废铜 -> 线缆/电网/新能源/地产后周期。关注TC、进口窗口、社库和下游开工。",
        "PB": "产业链传导：铅矿/再生铅 -> 精铅 -> 铅酸电池 -> 汽车/电动车替换需求。关注再生铅利润、电池开工和季节性补库。",
        "OCT": "产业链传导：原油/丙烯/合成气 -> 丁辛醇装置 -> 辛醇 -> DOP/DOTP/丙烯酸酯/溶剂。关注装置开工、增塑剂需求和华东/华南区域价差。",
    }.get(product.code, "产业链传导：上游成本、库存和终端订单共同影响价格。")
    return f"{chain}{basis_hint}"


def build_macro_view(db: Session, product: Product, metrics: ProductMetrics) -> str:
    snapshots = latest_macro_snapshots(db)
    return (
        f"{_fx_view(snapshots.get('USD_CNY'))}"
        f"{_economy_view(snapshots.get('CHINA_PMI'), snapshots.get('US_PMI'), product)}"
        f"{_crude_view(snapshots.get('BRENT'), product)}"
        f"{_chain_view(product, metrics)}"
    )


def build_macro_overview(db: Session, product_count: int, strong_count: int, weak_count: int, oi_up_count: int, macro_bias: str) -> str:
    snapshots = latest_macro_snapshots(db)
    usd = snapshots.get("USD_CNY")
    brent = snapshots.get("BRENT")
    china = snapshots.get("CHINA_PMI")
    us = snapshots.get("US_PMI")
    return "\n".join(
        [
            f"宏观快照：美元兑人民币{_row_text(usd)}；布伦特原油{_row_text(brent)}；中国PMI{_row_text(china)}；美国PMI{_row_text(us)}。",
            f"商品联动观察：{product_count}个品种中{strong_count}个主力合约上涨、{weak_count}个下跌，资金持仓增加品种{oi_up_count}个，整体呈{macro_bias}格局。",
            "宏观传导：人民币汇率影响进口成本和美元计价原料，原油影响化工、油脂和能源成本，中美经济周期分别影响国内工业需求、终端订单、出口链条和全球风险偏好。",
            "采购节奏：宏观信号未与产业链库存、订单和基差形成共振时，以订单覆盖和现金流安全为约束，避免一次性抬高库存。",
        ]
    )
