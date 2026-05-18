import math
from typing import Dict, List, Optional, Tuple


SCORE_MAX = 92.0


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(out):
        return default
    return out


def _clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def _log_score(value: float, target: float, weight: float) -> float:
    value = max(0.0, _to_float(value))
    target = max(1.0, target)
    return min(weight, weight * (math.log1p(value) / math.log1p(target)))


def parse_risk_flags(flags) -> List[str]:
    if flags is None:
        return []
    if isinstance(flags, list):
        return [str(flag).strip() for flag in flags if str(flag).strip()]
    if isinstance(flags, tuple) or isinstance(flags, set):
        return [str(flag).strip() for flag in flags if str(flag).strip()]
    text = str(flags).strip()
    if not text or text.lower() in {"nan", "none", "unknown"}:
        return []
    return [flag.strip() for flag in text.split(",") if flag.strip()]


def volume_liquidity_ratio(row: Dict) -> float:
    liq = _to_float(row.get("liquidity_usd"))
    vol24 = _to_float(row.get("volume_24h"))
    if liq <= 0:
        return float("inf") if vol24 > 0 else 0.0
    return vol24 / liq


def risk_flags(row: Dict) -> List[str]:
    flags: List[str] = []
    cap = _to_float(row.get("cap") or row.get("market_cap") or row.get("fdv"))
    liq = _to_float(row.get("liquidity_usd"))
    txns = _to_float(row.get("txns_24h"))
    buys = _to_float(row.get("buys_24h"))
    sells = _to_float(row.get("sells_24h"))
    move = abs(_to_float(row.get("price_change_24h")))
    vol_liq_ratio = volume_liquidity_ratio(row)

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


def combined_risk_flags(row: Dict) -> List[str]:
    flags = []
    for flag in parse_risk_flags(row.get("risk_flags")) + risk_flags(row):
        if flag not in flags:
            flags.append(flag)
    return flags


def compute_risk_level(row: Dict, flags: Optional[List[str]] = None) -> str:
    flags = parse_risk_flags(flags) if flags is not None else combined_risk_flags(row)
    flag_count = len(flags)

    if "volume_liquidity_ratio_extreme" in flags or flag_count >= 3:
        return "Extreme"
    if "no_sells_detected" in flags:
        return "High"
    if flag_count == 2:
        return "High"
    if flag_count == 1:
        return "Medium"
    return "Low"


def _component_scores(row: Dict) -> Dict[str, float]:
    x_mentions = _to_float(row.get("x_mentions"))
    x_engagement = _to_float(row.get("x_engagement"))
    unique_tweets = _to_float(row.get("unique_tweets"))
    unique_authors = _to_float(row.get("unique_authors")) or unique_tweets
    ca_mentions = _to_float(row.get("ca_mentions"))
    vol24 = _to_float(row.get("volume_24h"))
    vol1 = _to_float(row.get("volume_1h"))
    txns = _to_float(row.get("txns_24h"))
    cap = _to_float(row.get("cap") or row.get("market_cap") or row.get("fdv"))
    liq = _to_float(row.get("liquidity_usd"))

    cap_quality = _clamp(100 - (cap / 50_000), 0, 100) if cap > 0 else 0.0
    return {
        "x_mentions": _log_score(x_mentions, target=18, weight=18),
        "unique_authors": _log_score(unique_authors, target=10, weight=18),
        "x_engagement": _log_score(x_engagement, target=1_500, weight=10),
        "ca_mentions": _log_score(ca_mentions, target=6, weight=7),
        "volume_24h": _log_score(vol24, target=300_000, weight=11),
        "volume_1h": _log_score(vol1, target=40_000, weight=5),
        "txns_24h": _log_score(txns, target=900, weight=7),
        "liquidity_usd": _log_score(liq, target=180_000, weight=7),
        "cap_quality": cap_quality * 0.035,
    }


def _penalty_scores(row: Dict, flags: List[str], risk_level: str) -> Dict[str, float]:
    weights = {
        "ultra_low_mcap": 8,
        "very_low_liquidity": 15,
        "volume_liquidity_ratio_too_high": 24,
        "volume_liquidity_ratio_extreme": 42,
        "extreme_price_move": 30,
        "thin_txns_big_move": 18,
        "no_sells_detected": 22,
        "buy_sell_ratio_extreme_buy": 14,
        "buy_sell_ratio_extreme_sell": 14,
    }
    penalties = {f"flag:{flag}": weights.get(flag, 8) for flag in flags}

    x_mentions = _to_float(row.get("x_mentions"))
    x_engagement = _to_float(row.get("x_engagement"))
    unique_tweets = _to_float(row.get("unique_tweets"))
    unique_authors = _to_float(row.get("unique_authors")) or unique_tweets

    if x_mentions <= 0:
        penalties["x_mentions_missing"] = 28
    elif x_mentions == 1:
        penalties["x_mentions_single"] = 26
    elif x_mentions == 2:
        penalties["x_mentions_low"] = 10

    if unique_authors <= 0:
        penalties["unique_authors_missing"] = 18
    elif unique_authors <= 1:
        penalties["unique_authors_single"] = 18

    if x_engagement <= 0:
        penalties["x_engagement_zero"] = 14

    if len(flags) >= 2:
        penalties["multiple_flags"] = 18
    if len(flags) >= 3:
        penalties["many_flags"] = 35

    if risk_level == "High":
        penalties["risk_level_high"] = 14
    elif risk_level == "Extreme":
        penalties["risk_level_extreme"] = 32
    return penalties


def _format_breakdown(components: Dict[str, float], penalties: Dict[str, float], base: float, penalty: float, raw: float, score: float, risk_level: str) -> str:
    component_text = ",".join(f"{k}:{v:.2f}" for k, v in components.items())
    penalty_text = ",".join(f"{k}:{v:.2f}" for k, v in penalties.items()) or "none"
    return (
        f"base={base:.2f};penalty={penalty:.2f};raw={raw:.2f};"
        f"score_cap={SCORE_MAX:.2f};risk_level={risk_level};final={score:.2f};"
        f"components=[{component_text}];penalties=[{penalty_text}]"
    )


def compute_score_details(row: Dict) -> Dict:
    row = dict(row)
    unique_tweets = _to_float(row.get("unique_tweets"))
    unique_authors = _to_float(row.get("unique_authors")) or unique_tweets
    row["unique_authors"] = unique_authors

    flags = combined_risk_flags(row)
    risk_level = compute_risk_level(row, flags)
    components = _component_scores(row)
    penalties = _penalty_scores(row, flags, risk_level)

    base = sum(components.values())
    penalty = sum(penalties.values())
    raw = max(0.0, base - penalty)
    score = min(SCORE_MAX, raw * 0.88)
    if risk_level == "High":
        score = min(score, 65.0)
    elif risk_level == "Extreme":
        score = min(score, 20.0)

    score = round(_clamp(score), 2)
    ratio = volume_liquidity_ratio(row)
    ratio_value = round(ratio, 4) if math.isfinite(ratio) else ratio
    return {
        "early_gem_score": score,
        "base_score": round(base, 2),
        "penalty_score": round(penalty, 2),
        "risk_flags": flags,
        "risk_level": risk_level,
        "flag_count": len(flags),
        "volume_liquidity_ratio": ratio_value,
        "unique_authors": unique_authors,
        "score_breakdown": _format_breakdown(components, penalties, base, penalty, raw, score, risk_level),
    }


def compute_early_gem_score(row: Dict) -> Tuple[float, float, List[str]]:
    details = compute_score_details(row)
    return details["early_gem_score"], details["base_score"], details["risk_flags"]
