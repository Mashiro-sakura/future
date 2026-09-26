from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Iterable

from sqlalchemy.orm import Session
import requests

from app.config import get_settings
from app.models import FuturesPrice, InventorySnapshot, MacroSnapshot, OperatingRateSnapshot, Product, SpotPrice, SyncLog
from app.services.policy_events import sync_daily_policy_events


@dataclass
class FuturesRow:
    trade_date: date
    contract_code: str
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float
    settlement_price: float | None
    volume: float | None
    open_interest: float | None
    source: str


@dataclass
class SpotRow:
    trade_date: date
    price: float
    region: str
    source: str


@dataclass
class InventoryRow:
    trade_date: date
    social_inventory: float | None
    factory_inventory: float | None
    inventory_unit: str
    source: str


@dataclass
class MacroRow:
    trade_date: date
    indicator_code: str
    indicator_name: str
    value: float
    change_pct: float | None
    unit: str
    source: str


@dataclass
class OperatingRateRow:
    trade_date: date
    operating_rate: float | None
    unit: str
    source: str


BASE_PRICES = {
    "PTA": 5850.0,
    "PVC": 5650.0,
    "LLDPE": 8200.0,
    "PP": 7450.0,
    "PB": 16000.0,
    "P": 9300.0,
    "PL": 7100.0,
    "PX": 7750.0,
    "CU": 103000.0,
    "OCT": 8200.0,
}

MAIN_MONTHS = (1, 5, 9)
PRODUCT_CN_NAMES = {
    "PTA": "PTA",
    "PVC": "PVC",
    "LLDPE": "塑料",
    "PP": "聚丙烯",
    "PB": "铅",
    "P": "棕榈油",
    "PL": "丙烯",
    "PX": "对二甲苯",
    "CU": "铜",
    "OCT": "辛醇",
}
SPOT_REGIONS = ("华东", "华南", "西南")
REGIONAL_SPOT_OFFSETS = {"华东": 0.0, "华南": 28.0, "西南": -22.0}
# futures_spot_price 返回的是交易所品种代码（TA/V/L/PP...），按 spot_symbol 映射
AKSHARE_SPOT_SYMBOL_MAP = {
    "PTA": "TA",
    "PVC": "V",
    "LLDPE": "L",
    "PP": "PP",
    "沪铅": "PB",
    "棕榈油": "P",
    "丙烯": "PL",
    "PX": "PX",
    "沪铜": "CU",
}
# 日常 sync 现货只补最近几个交易日，长历史一律走 scripts/backfill_history.py
SPOT_SYNC_LOOKBACK_DAYS = 5
MACRO_BASES = {
    "USD_CNY": ("美元兑人民币", 7.18, ""),
    "BRENT": ("布伦特原油", 82.0, "美元/桶"),
    "CHINA_PMI": ("中国制造业PMI", 50.2, ""),
    "US_PMI": ("美国制造业PMI", 49.8, ""),
}
OPERATING_RATE_BASES = {
    "PTA": 78.0,
    "PX": 76.0,
    "PVC": 73.0,
    "LLDPE": 82.0,
    "PP": 80.0,
    "PL": 74.0,
    "P": 69.0,
    "CU": 86.0,
    "PB": 64.0,
    "OCT": 68.0,
}

SINA_DAILY_URL = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_DATA=/InnerFuturesNewService.getDailyKLine"
SINA_REALTIME_URL = "http://hq.sinajs.cn/list={symbols}"
SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.sina.com.cn/",
}


def _float(value: object, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt != "%Y%m%d" else text[:8], fmt).date()
        except ValueError:
            continue
    return None


def _pick(row: dict[str, object], names: Iterable[str]) -> object | None:
    lower_map = {str(key).strip().lower(): key for key in row.keys()}
    for name in names:
        key = lower_map.get(name.lower())
        if key is not None:
            return row.get(key)
    return None


def _has_futures(product: Product) -> bool:
    return bool((product.futures_symbol or "").strip()) and product.exchange != "SPOT"


def _contract_prefix(product: Product) -> str:
    return re.sub(r"\d+$", "", product.futures_symbol or "").upper()


def _next_main_contract(product: Product, current: date | None = None) -> str:
    if not _has_futures(product):
        return ""
    current = current or date.today()
    year = current.year
    month = next((item for item in MAIN_MONTHS if item >= current.month), MAIN_MONTHS[0])
    if month < current.month:
        year += 1
    return f"{_contract_prefix(product)}{str(year)[-2:]}{month:02d}"


def _contract_candidate_codes(prefix: str, current: date | None = None, months_forward: int = 18) -> list[str]:
    current = current or date.today()
    candidates: list[str] = []
    for offset in range(months_forward):
        month_index = current.month - 1 + offset
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        candidates.append(f"{prefix.upper()}{str(year)[-2:]}{month:02d}")
    return candidates


def _normalize_contract_code(product: Product, value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper().replace(" ", "")
    if not text:
        return None
    prefix = _contract_prefix(product)
    if text.startswith(prefix) and text.endswith("0"):
        return None
    match = re.search(rf"({prefix}\d{{3,4}})", text, flags=re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).upper()
    if len(raw) == len(prefix) + 3:
        return f"{prefix}2{raw[-3:]}"
    return raw


def _contract_symbol_variants(contract_code: str) -> list[str]:
    variants = [contract_code.upper()]
    match = re.match(r"^([A-Z]+)(\d{4})$", contract_code.upper())
    if match:
        prefix, digits = match.groups()
        if digits.startswith("2"):
            variants.append(f"{prefix}{digits[1:]}")
    return list(dict.fromkeys(variants))


def _resolve_main_contract_from_realtime(product: Product) -> str | None:
    import akshare as ak  # type: ignore

    functions = [
        ("futures_zh_realtime", {"symbol": PRODUCT_CN_NAMES.get(product.code, product.code)}),
        ("futures_zh_spot", {"symbol": product.futures_symbol, "market": "CF", "adjust": "0"}),
    ]
    prefix = _contract_prefix(product)
    candidates: list[tuple[float, str]] = []
    for function_name, kwargs in functions:
        func = getattr(ak, function_name, None)
        if func is None:
            continue
        try:
            df = func(**kwargs)
        except Exception:
            continue
        if df is None or getattr(df, "empty", True):
            continue
        for record in df.to_dict("records"):
            code = (
                _normalize_contract_code(product, _pick(record, ["symbol", "合约", "代码", "contract", "contract_code"]))
                or _normalize_contract_code(product, _pick(record, ["name", "名称", "品种"]))
            )
            if not code or not code.startswith(prefix):
                continue
            oi = _float(_pick(record, ["hold", "open_interest", "持仓量", "持仓"]))
            volume = _float(_pick(record, ["volume", "成交量"]))
            candidates.append((oi or volume or 0, code))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _rows_from_records(records: list[dict[str, object]], product: Product, contract_code: str, days: int, source: str) -> list[FuturesRow]:
    rows: list[FuturesRow] = []
    for record in records[-days:]:
        trade_date = _parse_date(_pick(record, ["date", "日期", "trade_date"]))
        close_price = _float(_pick(record, ["close", "收盘价", "close_price"]))
        if not trade_date or close_price is None:
            continue
        rows.append(
            FuturesRow(
                trade_date=trade_date,
                contract_code=contract_code,
                open_price=_float(_pick(record, ["open", "开盘价", "open_price"])),
                high_price=_float(_pick(record, ["high", "最高价", "high_price"])),
                low_price=_float(_pick(record, ["low", "最低价", "low_price"])),
                close_price=close_price,
                settlement_price=_float(_pick(record, ["settle", "settlement", "结算价", "动态结算价"])),
                volume=_float(_pick(record, ["volume", "成交量"])),
                open_interest=_float(_pick(record, ["hold", "open_interest", "持仓量"])),
                source=source,
            )
        )
    return rows


def _fetch_daily_rows_from_akshare_symbol(symbol: str, product: Product, contract_code: str, days: int) -> list[FuturesRow]:
    import akshare as ak  # type: ignore

    df = ak.futures_zh_daily_sina(symbol=symbol)
    if df is None or df.empty:
        return []
    return _rows_from_records(df.to_dict("records"), product, contract_code, days, "akshare:sina-main-contract")


def _extract_jsonp_array(text: str) -> list[dict[str, object]]:
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        return []
    data = json.loads(text[start : end + 1])
    return data if isinstance(data, list) else []


def _fetch_daily_rows_from_sina_symbol(symbol: str, product: Product, contract_code: str, days: int) -> list[FuturesRow]:
    response = requests.get(SINA_DAILY_URL, params={"symbol": symbol}, headers=SINA_HEADERS, timeout=(3, 8))
    response.raise_for_status()
    records = _extract_jsonp_array(response.text)
    if not records:
        return []
    return _rows_from_records(records, product, contract_code, days, "sina-main-contract")


def _parse_sina_realtime_text(text: str) -> list[list[str]]:
    quotes: list[list[str]] = []
    for item in text.split(";"):
        if "=" not in item:
            continue
        payload = item.split("=", 1)[1].strip().strip('"')
        if not payload:
            continue
        quotes.append(payload.split(","))
    return quotes


def _parse_sina_realtime_quote_items(text: str) -> list[tuple[str, list[str]]]:
    quotes: list[tuple[str, list[str]]] = []
    for item in text.split(";"):
        match = re.search(r"hq_str_nf_([A-Z0-9]+)\s*=\s*\"(.*)\"", item)
        if not match:
            continue
        symbol, payload = match.groups()
        if not payload:
            continue
        quotes.append((symbol.upper(), payload.split(",")))
    return quotes


def _row_from_sina_realtime_fields(fields: list[str], contract_code: str) -> FuturesRow | None:
    if len(fields) < 18:
        return None
    close_price = _float(fields[8]) or _float(fields[5])
    trade_date = _parse_date(fields[17])
    if close_price is None or not trade_date:
        return None
    return FuturesRow(
        trade_date=trade_date,
        contract_code=contract_code,
        open_price=_float(fields[2]),
        high_price=_float(fields[3]),
        low_price=_float(fields[4]),
        close_price=close_price,
        settlement_price=_float(fields[9]),
        volume=_float(fields[14]),
        open_interest=_float(fields[13]),
        source="sina-main-contract-realtime",
    )


def _fetch_realtime_rows_from_sina_symbols(symbols: list[str]) -> list[tuple[str, FuturesRow]]:
    if not symbols:
        return []
    response = requests.get(
        SINA_REALTIME_URL.format(symbols=",".join(f"nf_{symbol}" for symbol in symbols)),
        headers=SINA_HEADERS,
        timeout=(2, 5),
    )
    response.raise_for_status()
    rows: list[tuple[str, FuturesRow]] = []
    for symbol, fields in _parse_sina_realtime_quote_items(response.text):
        row = _row_from_sina_realtime_fields(fields, symbol)
        if row:
            rows.append((symbol, row))
    return rows


def _resolve_main_contract_from_sina(product: Product) -> str | None:
    candidates = _contract_candidate_codes(_contract_prefix(product))
    rows = _fetch_realtime_rows_from_sina_symbols(candidates)
    if not rows:
        return None
    rows.sort(key=lambda item: ((item[1].open_interest or 0), (item[1].volume or 0)), reverse=True)
    return rows[0][0]


def _fetch_realtime_row_from_sina_symbol(symbol: str, contract_code: str) -> FuturesRow | None:
    rows = _fetch_realtime_rows_from_sina_symbols([symbol])
    for _, row in rows:
        row.contract_code = contract_code
        return row
    return None


def _fetch_daily_rows_from_main_sina(product: Product, days: int) -> list[FuturesRow]:
    """主力连续合约日线（futures_main_sina，symbol 形如 TA0）。

    与 scripts/backfill_history.py 同源同 tag，自动处理换月；
    contract_code 如实标注为主力连续 symbol（TA0），非具体合约。
    """
    import akshare as ak  # type: ignore

    symbol = (product.futures_symbol or "").strip().upper()
    if not symbol:
        return []
    df = ak.futures_main_sina(symbol=symbol)
    if df is None or df.empty:
        return []
    return _rows_from_records(df.to_dict("records"), product, symbol, days, "akshare:sina-main-contract")


_realtime_cache: dict[str, object] = {"ts": 0.0, "data": None}
REALTIME_CACHE_TTL_SECONDS = 60


def fetch_realtime_main_quotes(products: list[Product], ttl: int = REALTIME_CACHE_TTL_SECONDS) -> dict[str, FuturesRow]:
    """盘中准实时：新浪快照透传（不写库），模块级 60s 缓存防打爆上游。

    每品种一次批量请求查全部候选合约，按持仓/成交量挑主力。
    上游失败时回退旧缓存（stale 总比白屏强），全无可返回空 dict。
    """
    import time

    now = time.time()
    cached = _realtime_cache.get("data")
    if cached is not None and now - float(_realtime_cache["ts"]) < ttl:
        return cached  # type: ignore[return-value]
    quotes: dict[str, FuturesRow] = {}
    for product in products:
        if not _has_futures(product):
            continue
        try:
            rows = _fetch_realtime_rows_from_sina_symbols(_contract_candidate_codes(_contract_prefix(product)))
            if not rows:
                continue
            rows.sort(key=lambda item: ((item[1].open_interest or 0), (item[1].volume or 0)), reverse=True)
            quotes[product.code] = rows[0][1]
        except Exception:
            continue
    if quotes:
        _realtime_cache["ts"] = now
        _realtime_cache["data"] = quotes
        return quotes
    return cached or {}  # type: ignore[return-value]


def _fallback_futures(product: Product, days: int = 60) -> list[FuturesRow]:
    if not _has_futures(product):
        return []
    base = BASE_PRICES.get(product.code, 7000.0)
    contract_code = _next_main_contract(product)
    rows: list[FuturesRow] = []
    start = date.today() - timedelta(days=days - 1)
    product_offset = sum(ord(ch) for ch in product.code) % 17
    for index in range(days):
        day = start + timedelta(days=index)
        wave = math.sin((index + product_offset) / 5) * base * 0.012
        drift = (index - days / 2) * base * 0.00025
        close_price = round(base + wave + drift, 2)
        open_price = round(close_price * (1 - 0.002), 2)
        high_price = round(close_price * (1 + 0.006), 2)
        low_price = round(close_price * (1 - 0.007), 2)
        volume = round(58_000 + product_offset * 700 + index * 420 + abs(wave) * 4, 0)
        open_interest = round(112_000 + product_offset * 1300 + index * 360 + math.cos(index / 4) * 2200, 0)
        rows.append(
            FuturesRow(
                trade_date=day,
                contract_code=contract_code,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                settlement_price=round((high_price + low_price + close_price) / 3, 2),
                volume=volume,
                open_interest=open_interest,
                source="fallback-demo",
            )
        )
    return rows


def _fallback_spot(product: Product, days: int = 60) -> list[SpotRow]:
    product_offset = sum(ord(ch) for ch in product.code) % 11
    base = BASE_PRICES.get(product.code, 7000.0)
    rows: list[SpotRow] = []
    start = date.today() - timedelta(days=days - 1)
    for index in range(days):
        day = start + timedelta(days=index)
        wave = math.sin((index + product_offset) / 5) * base * 0.01
        drift = (index - days / 2) * base * 0.00022
        reference_price = round(base + wave + drift, 2)
        basis = math.sin((index + product_offset) / 6) * 85 + (product_offset - 5) * 12
        huadong_price = reference_price + basis
        for region in SPOT_REGIONS:
            regional_wave = math.sin((index + product_offset + len(region)) / 8) * 8
            rows.append(
                SpotRow(
                    trade_date=day,
                    price=round(huadong_price + REGIONAL_SPOT_OFFSETS[region] + regional_wave, 2),
                    region=region,
                    source="fallback-demo",
                )
            )
    return rows


def _fallback_inventory(product: Product, days: int = 60) -> list[InventoryRow]:
    product_offset = sum(ord(ch) for ch in product.code) % 13
    base_social = {
        "PTA": 420.0,
        "PVC": 96.0,
        "LLDPE": 62.0,
        "PP": 70.0,
        "PB": 6.8,
        "P": 58.0,
        "PL": 12.0,
        "PX": 135.0,
        "CU": 18.0,
        "OCT": 18.0,
    }.get(product.code, 50.0)
    base_factory = {
        "PTA": 82.0,
        "PVC": 41.0,
        "LLDPE": 28.0,
        "PP": 32.0,
        "PB": 3.2,
        "P": 24.0,
        "PL": 7.0,
        "PX": 48.0,
        "CU": 7.5,
        "OCT": 7.0,
    }.get(product.code, 20.0)
    rows: list[InventoryRow] = []
    start = date.today() - timedelta(days=days - 1)
    for index in range(days):
        cycle = math.sin((index + product_offset) / 7)
        trend = math.cos((index + product_offset) / 17)
        social = round(max(base_social * (1 + cycle * 0.045 + trend * 0.018), 0.01), 2)
        factory = round(max(base_factory * (1 + math.sin((index + product_offset) / 6) * 0.055 - trend * 0.012), 0.01), 2)
        rows.append(
            InventoryRow(
                trade_date=start + timedelta(days=index),
                social_inventory=social,
                factory_inventory=factory,
                inventory_unit="万吨",
                source="fallback-demo",
            )
        )
    return rows


def _fallback_macro(days: int = 60) -> list[MacroRow]:
    rows: list[MacroRow] = []
    start = date.today() - timedelta(days=days - 1)
    previous: dict[str, float] = {}
    for index in range(days):
        day = start + timedelta(days=index)
        for offset, (code, (name, base, unit)) in enumerate(MACRO_BASES.items()):
            wave = math.sin((index + offset * 3) / 9)
            trend = math.cos((index + offset * 2) / 21)
            if code == "USD_CNY":
                value = round(base + wave * 0.035 + trend * 0.018, 4)
            elif code == "BRENT":
                value = round(base * (1 + wave * 0.035 + trend * 0.012), 2)
            else:
                value = round(base + wave * 0.65 + trend * 0.18, 2)
            prior = previous.get(code)
            change_pct = round((value - prior) / prior * 100, 2) if prior not in (None, 0) else None
            rows.append(
                MacroRow(
                    trade_date=day,
                    indicator_code=code,
                    indicator_name=name,
                    value=value,
                    change_pct=change_pct,
                    unit=unit,
                    source="fallback-demo",
                )
            )
            previous[code] = value
    return rows


def _fallback_operating_rates(product: Product, days: int = 60) -> list[OperatingRateRow]:
    rows: list[OperatingRateRow] = []
    start = date.today() - timedelta(days=days - 1)
    product_offset = sum(ord(ch) for ch in product.code) % 19
    base = OPERATING_RATE_BASES.get(product.code, 75.0)
    for index in range(days):
        cycle = math.sin((index + product_offset) / 8) * 3.2
        trend = math.cos((index + product_offset) / 19) * 1.4
        rate = min(max(base + cycle + trend, 35.0), 98.0)
        rows.append(
            OperatingRateRow(
                trade_date=start + timedelta(days=index),
                operating_rate=round(rate, 2),
                unit="%",
                source="fallback-demo",
            )
        )
    return rows


def _fetch_futures_from_akshare(product: Product, days: int) -> list[FuturesRow]:
    """日线优先，实时行只补当日。

    铁律：任何情况下都不把 fallback-demo 合成历史混进返回结果——
    历史只能来自真实日线源，取不到就返回空（由上层决定是否整体降级）。
    """
    if not _has_futures(product):
        return []
    daily_rows: list[FuturesRow] = []
    # 1) 主力连续日线（与回填脚本同源，自动换月）
    try:
        daily_rows = _fetch_daily_rows_from_main_sina(product, days)
    except Exception:
        daily_rows = []
    # 2) 具体合约日线兜底（sina jsonp → akshare daily）
    if not daily_rows:
        main_contract = _resolve_main_contract_from_sina(product) or _next_main_contract(product)
        for symbol in _contract_symbol_variants(main_contract):
            try:
                daily_rows = _fetch_daily_rows_from_sina_symbol(symbol, product, main_contract, days)
                if daily_rows:
                    break
            except Exception:
                pass
            try:
                daily_rows = _fetch_daily_rows_from_akshare_symbol(symbol, product, main_contract, days)
                if daily_rows:
                    break
            except Exception:
                pass
    if not daily_rows:
        return []
    # 3) 实时行只在比最后一条日线更新时追加（盘中补当日，绝不伪造历史）
    try:
        main_contract = _resolve_main_contract_from_sina(product) or _next_main_contract(product)
        for symbol in _contract_symbol_variants(main_contract):
            realtime_row = _fetch_realtime_row_from_sina_symbol(symbol, main_contract)
            if realtime_row and realtime_row.trade_date > daily_rows[-1].trade_date:
                daily_rows.append(realtime_row)
                break
    except Exception:
        pass
    return daily_rows[-days:]


def _recent_weekdays(count: int, today: date | None = None) -> list[date]:
    """最近 count 个工作日（周末跳过；节假日由数据方返回空自然过滤）。"""
    today = today or date.today()
    days_found: list[date] = []
    cursor = today
    while len(days_found) < count:
        if cursor.weekday() < 5:
            days_found.append(cursor)
        cursor -= timedelta(days=1)
    return days_found


def _fetch_spot_from_akshare(product: Product, days: int) -> list[SpotRow]:
    """按交易日调用 ak.futures_spot_price(yyyymmdd) 取基准现货价。

    该接口一次返回全品种，华东记真实来源，华南/西南按固定偏移估算并打
    regional-estimate 标。日常 sync 只补最近 SPOT_SYNC_LOOKBACK_DAYS 个交易日，
    长历史回填走 scripts/backfill_history.py。
    """
    import akshare as ak  # type: ignore

    ak_symbol = AKSHARE_SPOT_SYMBOL_MAP.get((product.spot_symbol or "").strip())
    if not ak_symbol:
        return []
    lookback = max(1, min(days, SPOT_SYNC_LOOKBACK_DAYS))
    rows: list[SpotRow] = []
    for trade_day in _recent_weekdays(lookback):
        try:
            df = ak.futures_spot_price(trade_day.strftime("%Y%m%d"))
        except Exception:
            continue
        if df is None or getattr(df, "empty", True):
            continue
        for record in df.to_dict("records"):
            if str(_pick(record, ["symbol"]) or "").strip().upper() != ak_symbol:
                continue
            trade_date = _parse_date(_pick(record, ["date", "日期", "trade_date"])) or trade_day
            price = _float(_pick(record, ["spot_price", "price", "现货价格", "价格"]))
            if price is None:
                continue
            rows.extend(
                SpotRow(
                    trade_date=trade_date,
                    price=round(price + REGIONAL_SPOT_OFFSETS[region], 2),
                    region=region,
                    source="akshare:futures_spot_price" if region == "华东" else "akshare:futures_spot_price:regional-estimate",
                )
                for region in SPOT_REGIONS
            )
            break
    return rows


def fetch_futures_prices(product: Product, days: int = 60) -> list[FuturesRow]:
    if not _has_futures(product):
        return []
    if get_settings().use_akshare:
        try:
            rows = _fetch_futures_from_akshare(product, days)
            if rows:
                return rows
        except Exception:
            pass
    return _fallback_futures(product, days)


def fetch_spot_prices(product: Product, days: int = 60) -> list[SpotRow]:
    if get_settings().use_akshare:
        try:
            rows = _fetch_spot_from_akshare(product, days)
            if rows:
                return rows
        except Exception:
            pass
    return _fallback_spot(product, days)


def fetch_inventory_snapshots(product: Product, days: int = 60) -> list[InventoryRow]:
    return _fallback_inventory(product, days)


def fetch_macro_snapshots(days: int = 60) -> list[MacroRow]:
    return _fallback_macro(days)


def fetch_operating_rate_snapshots(product: Product, days: int = 60) -> list[OperatingRateRow]:
    return _fallback_operating_rates(product, days)


def _upsert_futures(db: Session, product: Product, row: FuturesRow) -> None:
    existing = (
        db.query(FuturesPrice)
        .filter(FuturesPrice.product_code == product.code, FuturesPrice.trade_date == row.trade_date)
        .first()
    )
    values = {
        "open_price": row.open_price,
        "high_price": row.high_price,
        "low_price": row.low_price,
        "close_price": row.close_price,
        "settlement_price": row.settlement_price,
        "contract_code": row.contract_code,
        "volume": row.volume,
        "open_interest": row.open_interest,
        "source": row.source,
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
    else:
        db.add(FuturesPrice(product_code=product.code, trade_date=row.trade_date, **values))


def _upsert_spot(db: Session, product: Product, row: SpotRow) -> None:
    existing = (
        db.query(SpotPrice)
        .filter(
            SpotPrice.product_code == product.code,
            SpotPrice.trade_date == row.trade_date,
            SpotPrice.region == row.region,
        )
        .first()
    )
    values = {"price": row.price, "source": row.source}
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
    else:
        db.add(SpotPrice(product_code=product.code, trade_date=row.trade_date, region=row.region, **values))


def _upsert_inventory(db: Session, product: Product, row: InventoryRow) -> None:
    existing = (
        db.query(InventorySnapshot)
        .filter(InventorySnapshot.product_code == product.code, InventorySnapshot.trade_date == row.trade_date)
        .first()
    )
    values = {
        "social_inventory": row.social_inventory,
        "factory_inventory": row.factory_inventory,
        "inventory_unit": row.inventory_unit,
        "source": row.source,
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
    else:
        db.add(InventorySnapshot(product_code=product.code, trade_date=row.trade_date, **values))


def _upsert_macro(db: Session, row: MacroRow) -> None:
    existing = (
        db.query(MacroSnapshot)
        .filter(MacroSnapshot.indicator_code == row.indicator_code, MacroSnapshot.trade_date == row.trade_date)
        .first()
    )
    values = {
        "indicator_name": row.indicator_name,
        "value": row.value,
        "change_pct": row.change_pct,
        "unit": row.unit,
        "source": row.source,
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
    else:
        db.add(MacroSnapshot(indicator_code=row.indicator_code, trade_date=row.trade_date, **values))


def _upsert_operating_rate(db: Session, product: Product, row: OperatingRateRow) -> None:
    existing = (
        db.query(OperatingRateSnapshot)
        .filter(OperatingRateSnapshot.product_code == product.code, OperatingRateSnapshot.trade_date == row.trade_date)
        .first()
    )
    values = {
        "operating_rate": row.operating_rate,
        "unit": row.unit,
        "source": row.source,
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
    else:
        db.add(OperatingRateSnapshot(product_code=product.code, trade_date=row.trade_date, **values))


def sync_market_data(db: Session, job_type: str = "manual", days: int = 60) -> tuple[int, str]:
    products = db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.display_order).all()
    synced = 0
    messages: list[str] = []
    macro_rows = fetch_macro_snapshots(days)
    for row in macro_rows:
        _upsert_macro(db, row)
    messages.append(f"宏观指标: 写入/更新{len(macro_rows)}条")
    policy_event_count = sync_daily_policy_events(db, products)
    messages.append(f"政策消息: 写入/更新{policy_event_count}条")
    for product in products:
        log = SyncLog(job_type=job_type, product_code=product.code, status="running", message="同步开始")
        db.add(log)
        db.flush()
        try:
            futures_rows = fetch_futures_prices(product, days)
            spot_rows = fetch_spot_prices(product, days)
            inventory_rows = fetch_inventory_snapshots(product, days)
            operating_rate_rows = fetch_operating_rate_snapshots(product, days)
            for row in futures_rows:
                _upsert_futures(db, product, row)
            for row in spot_rows:
                _upsert_spot(db, product, row)
            for row in inventory_rows:
                _upsert_inventory(db, product, row)
            for row in operating_rate_rows:
                _upsert_operating_rate(db, product, row)
            log.status = "success"
            log.message = f"写入/更新期货{len(futures_rows)}条，现货{len(spot_rows)}条，库存{len(inventory_rows)}条，开工率{len(operating_rate_rows)}条"
            synced += 1
            messages.append(f"{product.code}: {log.message}")
        except Exception as exc:
            log.status = "failed"
            log.message = f"同步失败：{exc}"
            messages.append(f"{product.code}: {log.message}")
        finally:
            log.ended_at = datetime.utcnow()
    db.commit()
    return synced, "；".join(messages)


def import_spot_csv(db: Session, content: bytes) -> tuple[int, str]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    required = {"product_code", "trade_date", "price"}
    missing = required.difference(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV缺少字段：{', '.join(sorted(missing))}")

    imported = 0
    product_map = {product.code: product for product in db.query(Product).all()}
    for record in reader:
        code = (record.get("product_code") or "").strip().upper()
        product = product_map.get(code)
        trade_date = _parse_date(record.get("trade_date"))
        price = _float(record.get("price"))
        if not product or not trade_date or price is None:
            continue
        _upsert_spot(
            db,
            product,
            SpotRow(
                trade_date=trade_date,
                price=price,
                region=(record.get("region") or "华东").strip() or "华东",
                source="csv-import",
            ),
        )
        imported += 1
    db.commit()
    return imported, f"成功导入{imported}条现货价格"
