from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(32))
    futures_symbol: Mapped[str] = mapped_column(String(16))
    spot_symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    futures_prices: Mapped[list["FuturesPrice"]] = relationship(back_populates="product")
    spot_prices: Mapped[list["SpotPrice"]] = relationship(back_populates="product")
    inventory_snapshots: Mapped[list["InventorySnapshot"]] = relationship(back_populates="product")
    operating_rates: Mapped[list["OperatingRateSnapshot"]] = relationship(back_populates="product")
    policy_events: Mapped[list["PolicyEvent"]] = relationship(back_populates="product")


class FuturesPrice(Base):
    __tablename__ = "futures_prices"
    __table_args__ = (UniqueConstraint("product_code", "trade_date", name="uq_futures_product_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(String(16), ForeignKey("products.code"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open_price: Mapped[float | None] = mapped_column(Float)
    high_price: Mapped[float | None] = mapped_column(Float)
    low_price: Mapped[float | None] = mapped_column(Float)
    close_price: Mapped[float] = mapped_column(Float)
    settlement_price: Mapped[float | None] = mapped_column(Float)
    contract_code: Mapped[str] = mapped_column(String(32), default="")
    volume: Mapped[float | None] = mapped_column(Float)
    open_interest: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    product: Mapped[Product] = relationship(back_populates="futures_prices")


class SpotPrice(Base):
    __tablename__ = "spot_prices"
    __table_args__ = (UniqueConstraint("product_code", "trade_date", "region", name="uq_spot_product_date_region"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(String(16), ForeignKey("products.code"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[float] = mapped_column(Float)
    region: Mapped[str] = mapped_column(String(32), default="华东")
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    product: Mapped[Product] = relationship(back_populates="spot_prices")


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (UniqueConstraint("product_code", "trade_date", name="uq_inventory_product_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(String(16), ForeignKey("products.code"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    social_inventory: Mapped[float | None] = mapped_column(Float)
    factory_inventory: Mapped[float | None] = mapped_column(Float)
    inventory_unit: Mapped[str] = mapped_column(String(16), default="万吨")
    source: Mapped[str] = mapped_column(String(64), default="fallback-demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    product: Mapped[Product] = relationship(back_populates="inventory_snapshots")


class MacroSnapshot(Base):
    __tablename__ = "macro_snapshots"
    __table_args__ = (UniqueConstraint("indicator_code", "trade_date", name="uq_macro_indicator_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_code: Mapped[str] = mapped_column(String(32), index=True)
    indicator_name: Mapped[str] = mapped_column(String(64))
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="")
    source: Mapped[str] = mapped_column(String(64), default="fallback-demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class OperatingRateSnapshot(Base):
    __tablename__ = "operating_rate_snapshots"
    __table_args__ = (UniqueConstraint("product_code", "trade_date", name="uq_operating_rate_product_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(String(16), ForeignKey("products.code"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    operating_rate: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="%")
    source: Mapped[str] = mapped_column(String(64), default="fallback-demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    product: Mapped[Product] = relationship(back_populates="operating_rates")


class PolicyEvent(Base):
    __tablename__ = "policy_events"
    __table_args__ = (UniqueConstraint("product_code", "event_date", "category", "title", name="uq_policy_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(String(16), ForeignKey("products.code"), index=True)
    event_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    impact_level: Mapped[str] = mapped_column(String(16), default="关注")
    source: Mapped[str] = mapped_column(String(64), default="daily-policy-watch")
    url: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    product: Mapped[Product] = relationship(back_populates="policy_events")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("report_date", "session_name", name="uq_report_date_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    session_name: Mapped[str] = mapped_column(String(16), default="evening")
    title: Mapped[str] = mapped_column(String(128))
    market_summary: Mapped[str] = mapped_column(Text)
    price_behavior_analysis: Mapped[str] = mapped_column(Text, default="")
    fundamentals_analysis: Mapped[str] = mapped_column(Text, default="")
    macro_analysis: Mapped[str] = mapped_column(Text, default="")
    policy_analysis: Mapped[str] = mapped_column(Text, default="")
    product_analysis_payload: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="Recommendation.product_code"
    )

    @property
    def product_analyses(self) -> list[dict[str, str]]:
        try:
            payload = json.loads(self.product_analysis_payload or "[]")
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(16), ForeignKey("products.code"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    basis: Mapped[str] = mapped_column(Text)
    risk_note: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, default=70)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    report: Mapped[Report] = relationship(back_populates="recommendations")


class VolatilityDaily(Base):
    """期权波动率日频快照（V1: PTA/郑商所，IV 直接取交易所发布值）。

    定位=给期货终端加"波动率传感器"：IV 分位 + IV-HV 利差，全是结构描述。
    """

    __tablename__ = "volatility_daily"
    __table_args__ = (UniqueConstraint("product_code", "trade_date", name="uq_volatility_product_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(String(16), ForeignKey("products.code"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    underlying_month: Mapped[str] = mapped_column(String(16), default="")
    futures_ref: Mapped[float | None] = mapped_column(Float)
    atm_strike: Mapped[float | None] = mapped_column(Float)
    atm_iv: Mapped[float] = mapped_column(Float)
    call_iv: Mapped[float | None] = mapped_column(Float)
    put_iv: Mapped[float | None] = mapped_column(Float)
    hv20: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="czce")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32), default="manual")
    product_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PushLog(Base):
    __tablename__ = "push_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reports.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="wechat_work")
    status: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WechatMiniappSubscriber(Base):
    __tablename__ = "wechat_miniapp_subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    template_id: Mapped[str] = mapped_column(String(128))
    subscription_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_subscribed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
