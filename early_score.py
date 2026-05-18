import math
from typing import Dict, List, Optional, Tuple


def _clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def _log_score(value: float, target: float, weight: float) -> float:
    value = max(0.0, float(value or 0))
    target = max(1.0, target)
    return min(weight, weight * (math.log1p(value) / math.log1p(target)))


def _volume_liquidity_ratio(row: Dict) -> float:
    liq = float(row.get("liquidity_usd") or 0)
    vol24 = float(row.get("volume_24h") or 0)
    if liq <= 0:
        return float("inf") if vol24 > 0 else 0.0
    return vol24 / liq


def risk_flags(row: Dict) -> List[str]:
    flags: List[str] = []
    cap = float(row.get("cap") or row.get("market_cap") or row.get("fdv") or 0)
    liq = float(row.get("liquidity_usd") or 0)
    vol24 = float(row.get("volume_24h") or 0)
    txns = float(row.get("txns_24h") or 0)
    buys = float(row.get("buys_24h") or 0)
    sells = float(row.get("sells_24h") or 0)
    move = abs(float(row.get("price_change_24h") or 0))
    vol_liq_ratio = _volume_liquidity_ratio(row)

    if cap > 0 and cap < 500_000:
        flags.append("ultra_low_mcap")
    if liq < 10_000:
        flags.append("very_low_liquidity")
    if vol_liq_ratio > 20:
        flags.append("volume_liquidity_ratio_extreme")
    elif vol_liq_ratio > 8:
        flags.append("volume_liquidity_ratio_too_high")
    if move > 80:
        flags.append("extreme_price_move")
    if txns < 40 and move > 30:
        flags.append("thin_txns_big_move")
    if sells == 0 and buys > 0:
        flags.append("no_sells_detected")
    if sells > 0 and (buys / sells) > 8:
        flags.append("buy_sell_ratio_extreme_buy")
    if buys > 0 and (sells / buys) > 8:
        flags.append("buy_sell_ratio_extreme_sell")
    return flags


def compute_risk_level(row: Dict, flags: Optional[List[str]] = None) -> str:
    flags = flags if flags is not None else risk_flags(row)
    flag_count = len(flags)
    move = abs(float(row.get("price_change_24h") or 0))
    x_mentions = float(row.get("x_mentions") or 0)
    x_engagement = float(row.get("x_engagement") or 0)
    vol_liq_ratio = _volume_liquidity_ratio(row)

    if (
        flag_count >= 3
        or vol_liq_ratio > 20
        or move > 120
        or "no_sells_detected" in flags
    ):
        return "Extreme"
    if flag_count >= 2 or vol_liq_ratio > 8 or move > 80:
        return "High"
    if flag_count == 1 or x_mentions <= 1 or x_engagement <= 0:
        return "Medium"
    return "Low"


def _risk_penalty(row: Dict, flags: List[str]) -> float:
    weights = {
        "ultra_low_mcap": 8,
        "very_low_liquidity": 14,
        "volume_liquidity_ratio_too_high": 22,
        "volume_liquidity_ratio_extreme": 38,
        "extreme_price_move": 26,
        "thin_txns_big_move": 16,
        "no_sells_detected": 18,
        "buy_sell_ratio_extreme_buy": 14,
        "buy_sell_ratio_extreme_sell": 14,
    }
    penalty = sum(weights.get(flag, 8) for flag in flags)

    x_mentions = float(row.get("x_mentions") or 0)
    x_engagement = float(row.get("x_engagement") or 0)
    if x_mentions <= 0:
        penalty += 26
    elif x_mentions == 1:
        penalty += 22
    elif x_mentions == 2:
        penalty += 8

    if x_engagement <= 0:
        penalty += 12

    if len(flags) >= 2:
        penalty += 18
    if len(flags) >= 3:
        penalty += 32
    return penalty


def compute_early_gem_score(row: Dict) -> Tuple[float, float, List[str]]:
    x_mentions = float(row.get("x_mentions") or 0)
    x_engagement = float(row.get("x_engagement") or 0)
    unique_tweets = float(row.get("unique_tweets") or 0)
    unique_authors = float(row.get("unique_authors") or unique_tweets or 0)
    ca_mentions = float(row.get("ca_mentions") or 0)
    vol24 = float(row.get("volume_24h") or 0)
    vol1 = float(row.get("volume_1h") or 0)
    txns = float(row.get("txns_24h") or 0)
    cap = float(row.get("cap") or row.get("market_cap") or row.get("fdv") or 0)
    liq = float(row.get("liquidity_usd") or 0)

    cap_quality = 0.0
    if cap > 0:
        cap_quality = _clamp(100 - (cap / 50_000), 0, 100)

    base = (
        _log_score(x_mentions, target=14, weight=20)
        + _log_score(unique_authors, target=8, weight=18)
        + _log_score(x_engagement, target=1_200, weight=12)
        + _log_score(ca_mentions, target=5, weight=8)
        + _log_score(vol24, target=250_000, weight=12)
        + _log_score(vol1, target=35_000, weight=6)
        + _log_score(txns, target=800, weight=8)
        + _log_score(liq, target=150_000, weight=8)
        + (cap_quality * 0.04)
    )

    flags = risk_flags(row)
    penalty = _risk_penalty(row, flags)
    score = _clamp(base - penalty)
    if len(flags) >= 3:
        score = min(score, 18.0)
    return round(score, 2), round(base, 2), flags
