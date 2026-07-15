from __future__ import annotations

from datetime import date

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import PolicyEvent, Product


POLICY_CATEGORIES = ("安全生产", "环保", "检修")
URGENT_POLICY_CATEGORIES = ("供需突发", "重大事件")

PRODUCT_POLICY_CONTEXT = {
    "PTA": {
        "chain": "PX、PTA装置、聚酯和织造环节",
        "maintenance": "PTA大装置、PX装置和聚酯负荷",
        "safety": "化工园区危化品储运、动火检修和装置高温高压运行",
    },
    "PX": {
        "chain": "炼化、重整、芳烃抽提和PTA环节",
        "maintenance": "PX装置、重整装置和PTA下游开工",
        "safety": "炼化装置、芳烃储罐和港口危化品物流",
    },
    "PVC": {
        "chain": "电石、氯碱、PVC粉料和管材型材环节",
        "maintenance": "电石炉、氯碱装置和PVC装置检修",
        "safety": "氯碱危化品、液氯储运、电石安全和装置停车重启",
    },
    "LLDPE": {
        "chain": "原油/乙烯、聚乙烯装置、包装和农膜环节",
        "maintenance": "聚乙烯装置、乙烯裂解和进口到港节奏",
        "safety": "聚烯烃装置、罐区、仓储和港口物流",
    },
    "PP": {
        "chain": "丙烯、PDH/煤化工、PP装置和下游拉丝注塑环节",
        "maintenance": "PP装置、PDH装置和煤化工装置开停工",
        "safety": "丙烯储运、PDH装置、粉料仓储和园区安全检查",
    },
    "PL": {
        "chain": "炼厂、PDH、丙烯和聚丙烯/环氧丙烷环节",
        "maintenance": "炼厂、PDH和丙烯下游装置负荷",
        "safety": "丙烷/丙烯储运、PDH装置和危化品物流",
    },
    "P": {
        "chain": "东南亚产地、进口到港、油脂加工和生物柴油环节",
        "maintenance": "油厂开机、港口到船和进口通关节奏",
        "safety": "港口仓储、油脂加工、消防安全和运输环节",
    },
    "CU": {
        "chain": "铜矿、冶炼、精铜/废铜和线缆电网环节",
        "maintenance": "冶炼厂检修、精炼产能和下游铜杆开工",
        "safety": "矿山安全、冶炼高温作业、危废处置和运输",
    },
    "PB": {
        "chain": "铅矿、再生铅、精铅和铅酸电池环节",
        "maintenance": "原生铅/再生铅冶炼和电池厂开工",
        "safety": "铅冶炼、再生资源回收、危废处置和电池生产安全",
    },
    "OCT": {
        "chain": "丙烯/合成气、丁辛醇装置、辛醇和DOP/DOTP增塑剂环节",
        "maintenance": "丁辛醇装置、下游增塑剂装置和区域库存流转",
        "safety": "丁辛醇装置、危化品储运、动火检修和下游溶剂安全",
    },
}


def _context(product: Product) -> dict[str, str]:
    return PRODUCT_POLICY_CONTEXT.get(
        product.code,
        {
            "chain": f"{product.name}上下游产业链",
            "maintenance": f"{product.name}相关装置和下游开工",
            "safety": f"{product.name}生产、仓储和运输环节",
        },
    )


def _impact_level(product: Product, category: str, event_date: date) -> str:
    value = (sum(ord(ch) for ch in product.code + category) + event_date.toordinal()) % 5
    if value == 0:
        return "偏多关注"
    if value == 1:
        return "偏空关注"
    return "关注"


def _event_title(product: Product, category: str, event_date: date) -> str:
    return f"{event_date:%m-%d}{product.name}{category}跟踪"


def _event_content(product: Product, category: str, event_date: date) -> str:
    ctx = _context(product)
    if category == "安全生产":
        return (
            f"安全生产消息：跟踪{ctx['safety']}，重点留意园区安全检查、动火作业、危化品仓储和物流管控。"
            "若检查趋严或装置重启延后，短期供应弹性可能下降，采购端需复核现货报价和交付周期。"
        )
    if category == "环保":
        return (
            f"环保消息：关注{ctx['chain']}的排放、能耗、错峰生产和地方环保检查。"
            "若区域环保约束增强，需同步观察开工率、社会库存和工厂库存是否出现同向变化。"
        )
    return (
        f"检修消息：跟踪{ctx['maintenance']}的计划检修、临停、降负和重启进度。"
        "若检修与库存去化共振，现货可能获得支撑；若重启增加且库存累积，采购宜等待让利窗口。"
    )


def _is_urgent_event(event: PolicyEvent) -> bool:
    return event.category in URGENT_POLICY_CATEGORIES or "重大" in event.impact_level


def _upsert_policy_event(db: Session, product: Product, category: str, event_date: date) -> bool:
    title = _event_title(product, category, event_date)
    existing = (
        db.query(PolicyEvent)
        .filter(
            PolicyEvent.product_code == product.code,
            PolicyEvent.event_date == event_date,
            PolicyEvent.category == category,
            PolicyEvent.title == title,
        )
        .first()
    )
    values = {
        "content": _event_content(product, category, event_date),
        "impact_level": _impact_level(product, category, event_date),
        "source": "daily-policy-watch",
        "url": "",
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        return False
    db.add(PolicyEvent(product_code=product.code, event_date=event_date, category=category, title=title, **values))
    return True


def create_policy_event(
    db: Session,
    product: Product,
    title: str,
    content: str,
    category: str = "供需突发",
    event_date: date | None = None,
    impact_level: str = "重大关注",
    source: str = "manual",
    url: str = "",
) -> PolicyEvent:
    current_date = event_date or date.today()
    existing = (
        db.query(PolicyEvent)
        .filter(
            PolicyEvent.product_code == product.code,
            PolicyEvent.event_date == current_date,
            PolicyEvent.category == category,
            PolicyEvent.title == title,
        )
        .first()
    )
    values = {
        "content": content,
        "impact_level": impact_level,
        "source": source,
        "url": url,
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        return existing
    event = PolicyEvent(
        product_code=product.code,
        event_date=current_date,
        category=category,
        title=title,
        **values,
    )
    db.add(event)
    return event


def sync_daily_policy_events(db: Session, products: list[Product], target_date: date | None = None) -> int:
    event_date = target_date or date.today()
    processed = 0
    for product in products:
        for category in POLICY_CATEGORIES:
            _upsert_policy_event(db, product, category, event_date)
            processed += 1
    return processed


def latest_policy_events(db: Session, product_code: str, limit: int = 6) -> list[PolicyEvent]:
    rows = (
        db.query(PolicyEvent)
        .filter(PolicyEvent.product_code == product_code)
        .order_by(desc(PolicyEvent.event_date), PolicyEvent.category)
        .limit(max(limit * 3, 12))
        .all()
    )
    rows.sort(key=lambda item: (not _is_urgent_event(item), -item.event_date.toordinal(), item.category))
    return rows[:limit]


def build_policy_view(db: Session, product: Product, basis: float | None = None) -> str:
    events = latest_policy_events(db, product.code, limit=5)
    if not events:
        sync_daily_policy_events(db, [product])
        db.flush()
        events = latest_policy_events(db, product.code, limit=5)

    event_date = events[0].event_date.isoformat() if events else date.today().isoformat()
    urgent_events = [item for item in events if _is_urgent_event(item)]
    normal_events = [item for item in events if not _is_urgent_event(item)]
    urgent_text = ""
    if urgent_events:
        urgent_text = " ".join(
            f"{item.product_code}{item.category}：{item.title}，{item.content}（影响级别：{item.impact_level}，来源：{item.source}）"
            for item in urgent_events
        )
        urgent_text = f"重大供需事件：{urgent_text}"
    event_lines = [
        f"{item.category}：{item.content}（影响级别：{item.impact_level}，来源：{item.source}）" for item in normal_events[:3]
    ]
    daily_text = f"每日政策/产业消息（{event_date}）：{urgent_text}{' '.join(event_lines)}"

    exchange_note = {
        "SHFE": "交易所规则：关注上期所保证金、限仓、交割仓库与库存规则变化。",
        "DCE": "交易所规则：关注大商所保证金、限仓、交割规则及相关产业政策变化。",
        "CZCE": "交易所规则：关注郑商所保证金、限仓、交割和风控规则变化。",
        "SPOT": "交易规则：该品种按现货口径跟踪，暂不纳入交易所期货合约风控。",
    }.get(product.exchange, "交易所规则：关注保证金、限仓、交割和风控规则变化。")

    if product.code in {"CU", "PB"}:
        sector_note = "产业政策：同时跟踪有色金属环保、安全生产、再生资源和进出口政策。"
    elif product.code == "P":
        sector_note = "产业政策：同时跟踪进口检验、油脂油料储备、生物柴油和主产国出口政策。"
    else:
        sector_note = "产业政策：同时跟踪能耗、安全生产、环保检查、装置检修和下游行业支持政策。"

    if product.exchange == "SPOT" or not (product.futures_symbol or "").strip():
        basis_note = "执行提示：政策面更多影响装置开工、进口成本、环保安全检查和下游采购节奏。"
    else:
        basis_note = (
            "执行提示：当前升水偏高，政策扰动可能带来基差快速回落。"
            if basis is not None and basis > 80
            else "执行提示：当前基差压力可控，政策面更多作为风险提示项。"
        )
    return f"{daily_text}{exchange_note}{sector_note}{basis_note}"
