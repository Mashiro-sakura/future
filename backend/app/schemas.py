from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    code: str
    name: str
    futures_symbol: str
    spot_symbol: str
    exchange: str
    display_order: int

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    trade_date: date
    futures_contract: str | None = None
    futures_close: float | None = None
    spot_price: float | None = None
    open_interest: float | None = None
    volume: float | None = None


class ProductOverview(BaseModel):
    code: str
    name: str
    futures_contract: str | None = None
    futures_close: float | None = None
    spot_price: float | None = None
    basis_value: float | None = None
    futures_change_pct: float | None = None
    spot_change_pct: float | None = None
    open_interest_change_pct: float | None = None
    recommendation: str | None = None
    confidence: int | None = None


class RecommendationOut(BaseModel):
    id: int
    product_code: str
    action: str
    basis: str
    risk_note: str
    confidence: int

    model_config = {"from_attributes": True}


class ProductAnalysisOut(BaseModel):
    product_code: str
    price_behavior: str = ""
    fundamentals: str = ""
    macro: str = ""
    policy: str = ""
    conclusion: str = ""


class ReportOut(BaseModel):
    id: int
    report_date: date
    session_name: str
    title: str
    market_summary: str
    price_behavior_analysis: str = ""
    fundamentals_analysis: str = ""
    macro_analysis: str = ""
    policy_analysis: str = ""
    status: str
    generated_at: datetime
    published_at: datetime | None
    pushed_at: datetime | None
    product_analyses: list[ProductAnalysisOut] = []
    recommendations: list[RecommendationOut] = []

    model_config = {"from_attributes": True}


class OverviewOut(BaseModel):
    latest_report: ReportOut | None
    products: list[ProductOverview]


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RecommendationUpdate(BaseModel):
    id: int | None = None
    product_code: str
    action: str
    basis: str
    risk_note: str
    confidence: int = Field(ge=0, le=100)


class ReportUpdate(BaseModel):
    title: str | None = None
    market_summary: str | None = None
    price_behavior_analysis: str | None = None
    fundamentals_analysis: str | None = None
    macro_analysis: str | None = None
    policy_analysis: str | None = None
    recommendations: list[RecommendationUpdate] | None = None


class SyncOut(BaseModel):
    status: str
    synced_products: int
    message: str


class ImportOut(BaseModel):
    status: str
    imported: int
    message: str


class PushOut(BaseModel):
    status: str
    message: str


class PolicyEventCreate(BaseModel):
    product_codes: list[str] = Field(default_factory=list)
    event_date: date | None = None
    category: str = "供需突发"
    title: str
    content: str
    impact_level: str = "重大关注"
    source: str = "manual"
    url: str = ""
    push_now: bool = False
    session_name: str = "urgent"


class PolicyEventOut(BaseModel):
    id: int
    product_code: str
    event_date: date
    category: str
    title: str
    content: str
    impact_level: str
    source: str
    url: str

    model_config = {"from_attributes": True}


class PolicyEventCreateOut(BaseModel):
    status: str
    created: int
    events: list[PolicyEventOut]
    report_id: int | None = None
    push_status: str | None = None
    message: str


class SyncLogOut(BaseModel):
    id: int
    job_type: str
    product_code: str | None
    status: str
    message: str
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class PushLogOut(BaseModel):
    id: int
    report_id: int | None
    channel: str
    status: str
    message: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class LogsOut(BaseModel):
    sync_logs: list[SyncLogOut]
    push_logs: list[PushLogOut]


class MiniappSubscribeConfigOut(BaseModel):
    enabled: bool
    template_id: str | None = None
    message: str


class MiniappSubscriptionIn(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    template_id: str = Field(min_length=1, max_length=128)


class MiniappSubscriptionOut(BaseModel):
    status: str
    message: str
    subscription_count: int = 0


class BasisPoint(BaseModel):
    trade_date: date
    futures_contract: str | None = None
    futures_close: float | None = None
    spot_price: float | None = None
    basis_value: float | None = None


class BasisOverviewItem(BaseModel):
    code: str
    name: str
    basis_value: float
    basis_label: str
    futures_close: float | None = None
    spot_price: float | None = None
    futures_contract: str | None = None
    trade_date: date | None = None
    days_since_last: int = 0
    data_stale: bool = False
    percentile: float | None = None
    zone: str | None = None
    sample_days: int
    window: int


class BasisDetailOut(BaseModel):
    snapshot: BasisOverviewItem
    history: list[BasisPoint]
