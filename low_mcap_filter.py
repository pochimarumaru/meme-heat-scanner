import re
from typing import Dict, List


EXCLUDED_SYMBOLS = {
    "ADA",
    "AVAX",
    "BTC",
    "WBTC",
    "DOT",
    "ETH",
    "WETH",
    "LINK",
    "MATIC",
    "TON",
    "TRX",
    "XRP",
    "SOL",
    "WSOL",
    "BNB",
    "WBNB",
    "USDT",
    "USDC",
    "BUSD",
    "DAI",
    "FDUSD",
    "TUSD",
    "DOGE",
    "SHIB",
    "PEPE",
}

HISTORY_CAP_LIMIT = 10_000_000
CANDIDATE_CURRENT_CAP_LIMIT = 2_000_000


def _normalize_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (symbol or "").upper())


def exclusion_reason(row: Dict) -> str:
    symbol = _normalize_symbol(str(row.get("symbol") or ""))
    if symbol in EXCLUDED_SYMBOLS:
        return "major_symbol_noise"
    return ""


def is_major_symbol(symbol: str) -> bool:
    return _normalize_symbol(symbol) in EXCLUDED_SYMBOLS


def calc_cap(row: Dict) -> float:
    mc = float(row.get("market_cap") or 0)
    fdv = float(row.get("fdv") or 0)
    return mc if mc > 0 else fdv


def passes_low_mcap(row: Dict, mode: str = "balanced") -> bool:
    cap = calc_cap(row)
    return 0 < cap <= HISTORY_CAP_LIMIT


def current_cap_filter_pass(row: Dict) -> bool:
    return 0 < calc_cap(row) < CANDIDATE_CURRENT_CAP_LIMIT


def filter_candidates(rows: List[Dict], mode: str = "balanced") -> List[Dict]:
    out = []
    seen_pairs = set()
    for r in rows:
        r = dict(r)
        pair_address = r.get("pair_address")
        if pair_address and pair_address in seen_pairs:
            continue
        if pair_address:
            seen_pairs.add(pair_address)

        r["cap"] = calc_cap(r)
        r["exclusion_reason"] = exclusion_reason(r)
        if passes_low_mcap(r, mode=mode):
            out.append(r)
    return out
