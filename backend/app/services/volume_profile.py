"""成交量分布（Volume Profile）——订单流的免费近似。

定位纪律（2026-09-26 拍板）：
- 真·订单流（逐笔/Level-2 盘口墙）是付费数据的领地，不做（档3战场不买门票）。
- 本模块回答的是"哪里真刀真枪成交过"（已成事实的筹码），不回答"哪里挂着单"（会撤会跑）。
- 原料=新浪分钟线（仅回溯约 5 个交易日），所以这是"本周筹码分布"，不是长期成本区。
- "大单"近似=放量分钟 bar（成交量 ≥ 均值×BIG_VOLUME_MULT）单独累计，无逐笔数据时最诚实的近似。
- 不落库：分钟线窗口随时间滑动，计算结果即取即用，模块级缓存 CACHE_TTL 秒。

输出三件套：POC（成交量最大档=控制点）+ VAH/VAL（70% 价值区上下沿）+ 分档分布。
"""

from __future__ import annotations

import time
from datetime import datetime

import akshare as ak
from sqlalchemy.orm import Session

from app.models import Product

BIN_COUNT = 24  # 价格分档数
BIG_VOLUME_MULT = 2.0  # 放量 bar 阈值倍数
VALUE_AREA_PCT = 0.70  # 价值区覆盖率
CACHE_TTL_SECONDS = 300

# code -> (cached_at_epoch, payload)
_profile_cache: dict[str, tuple[float, dict]] = {}


def _fetch_minute_bars(symbol: str) -> list[dict]:
    """抓分钟线。上游失败返回空列表（调用方走缓存回退）。"""
    df = ak.futures_zh_minute_sina(symbol=symbol)
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def build_volume_profile(
    rows: list[dict],
    bin_count: int = BIN_COUNT,
    big_mult: float = BIG_VOLUME_MULT,
    va_pct: float = VALUE_AREA_PCT,
) -> dict | None:
    """分钟 bar → 成交量分布。bar 成交量按 (high+low)/2 中价归入最近档。"""
    bars = [
        r for r in rows
        if r.get("volume") and float(r["volume"]) > 0 and r.get("high") and r.get("low")
    ]
    if len(bars) < bin_count:
        return None
    pmin = min(float(r["low"]) for r in bars)
    pmax = max(float(r["high"]) for r in bars)
    if pmax <= pmin:
        return None
    bin_size = (pmax - pmin) / bin_count
    bins = [
        {
            "low": round(pmin + i * bin_size, 1),
            "high": round(pmin + (i + 1) * bin_size, 1),
            "price": round(pmin + (i + 0.5) * bin_size, 1),
            "volume": 0.0,
            "big_volume": 0.0,
        }
        for i in range(bin_count)
    ]
    vols = [float(r["volume"]) for r in bars]
    big_threshold = sum(vols) / len(vols) * big_mult
    for r in bars:
        mid = (float(r["high"]) + float(r["low"])) / 2
        idx = min(int((mid - pmin) / bin_size), bin_count - 1)
        v = float(r["volume"])
        bins[idx]["volume"] += v
        if v >= big_threshold:
            bins[idx]["big_volume"] += v
    total = sum(b["volume"] for b in bins)
    if total <= 0:
        return None
    poc_idx = max(range(bin_count), key=lambda i: bins[i]["volume"])
    # 价值区：从 POC 向两侧贪心扩展，每次并入较大邻档，直至覆盖 va_pct
    covered = bins[poc_idx]["volume"]
    up = down = poc_idx
    while covered < total * va_pct and (up < bin_count - 1 or down > 0):
        up_vol = bins[up + 1]["volume"] if up < bin_count - 1 else -1.0
        down_vol = bins[down - 1]["volume"] if down > 0 else -1.0
        if up_vol >= down_vol:
            up += 1
            covered += bins[up]["volume"]
        else:
            down -= 1
            covered += bins[down]["volume"]
    poc = bins[poc_idx]["price"]
    vah = bins[up]["high"]
    val = bins[down]["low"]
    last_close = float(bars[-1]["close"]) if bars[-1].get("close") else None
    position = None
    if last_close is not None:
        if last_close > vah:
            position = "高于价值区"
        elif last_close < val:
            position = "低于价值区"
        else:
            position = "价值区内"
    max_vol = max(b["volume"] for b in bins)
    for b in bins:
        b["volume"] = round(b["volume"])
        b["big_volume"] = round(b["big_volume"])
        b["pct"] = round(b["volume"] / total * 100, 1)
        b["is_poc"] = b["price"] == poc
    big_total = sum(b["big_volume"] for b in bins)
    return {
        "window_start": str(bars[0].get("datetime", "")),
        "window_end": str(bars[-1].get("datetime", "")),
        "bar_count": len(bars),
        "bin_size": round(bin_size, 1),
        "poc": poc,
        "vah": vah,
        "val": val,
        "last_close": last_close,
        "position": position,
        "total_volume": round(total),
        "big_volume_pct": round(big_total / total * 100, 1),
        "max_bin_volume": round(max_vol),
        "bins": bins,
    }


def volume_profile_snapshot(db: Session, code: str) -> dict | None:
    """读取某品种成交量分布（带缓存+失败回退）。纯现货/无分钟线品种返回 None。"""
    code = code.upper()
    product = db.query(Product).filter(Product.code == code, Product.is_active.is_(True)).first()
    symbol = (product.futures_symbol or "").strip().upper() if product else ""
    if not product or not symbol or product.exchange == "SPOT":
        return None
    now = time.time()
    cached = _profile_cache.get(code)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    try:
        rows = _fetch_minute_bars(symbol)
        payload = build_volume_profile(rows)
    except Exception:
        payload = None
    if payload is None:
        return cached[1] if cached else None  # 失败回退旧缓存
    payload["code"] = code
    payload["futures_symbol"] = symbol
    payload["server_time"] = datetime.now().isoformat()
    _profile_cache[code] = (now, payload)
    return payload
