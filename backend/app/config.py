from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_load_env_file()


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "期现分析推送系统"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./future_analysis.db"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "change-me-in-production"))
    token_expire_minutes: int = field(default_factory=lambda: int(os.getenv("TOKEN_EXPIRE_MINUTES", "720")))
    admin_username: str = field(default_factory=lambda: os.getenv("ADMIN_USERNAME", "admin"))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", "admin123"))
    wechat_work_webhook_url: str = field(default_factory=lambda: os.getenv("WECHAT_WORK_WEBHOOK_URL", ""))
    wechat_miniapp_subscribe_enabled: bool = field(
        default_factory=lambda: _bool_env("WECHAT_MINIAPP_SUBSCRIBE_ENABLED", True)
    )
    wechat_miniapp_appid: str = field(default_factory=lambda: os.getenv("WECHAT_MINIAPP_APPID", ""))
    wechat_miniapp_secret: str = field(default_factory=lambda: os.getenv("WECHAT_MINIAPP_SECRET", ""))
    wechat_subscribe_template_id: str = field(default_factory=lambda: os.getenv("WECHAT_SUBSCRIBE_TEMPLATE_ID", ""))
    wechat_subscribe_template_data: str = field(
        default_factory=lambda: os.getenv("WECHAT_SUBSCRIBE_TEMPLATE_DATA", "")
    )
    wechat_subscribe_page: str = field(
        default_factory=lambda: os.getenv("WECHAT_SUBSCRIBE_PAGE", "pages/report/detail?id={report_id}")
    )
    wechat_miniapp_state: str = field(default_factory=lambda: os.getenv("WECHAT_MINIAPP_STATE", "formal"))
    public_client_url: str = field(default_factory=lambda: os.getenv("PUBLIC_CLIENT_URL", "http://127.0.0.1:5174"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
            ).split(",")
            if origin.strip()
        )
    )
    use_akshare: bool = field(default_factory=lambda: _bool_env("USE_AKSHARE", True))
    scheduler_enabled: bool = field(default_factory=lambda: _bool_env("SCHEDULER_ENABLED", True))
    bootstrap_sample_data: bool = field(default_factory=lambda: _bool_env("BOOTSTRAP_SAMPLE_DATA", True))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
