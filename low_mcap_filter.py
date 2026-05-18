import re
from typing import Dict, List


MAJOR_SYMBOLS = {
    "BTC",
    "WBTC",
    "ETH",
    "WETH",
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
}


def _normalize_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (symbol or "").upper())


def is_major_symbol(symbol: str) -> bool:
    return _normalize_symbol(symbol) in MAJOR_SYMBOLS


def calc_cap(row: Dict) -> float:
    mc = float(row.get("market_cap") or 0)
    fdv = float(row.get("fdv") or 0)
    return mc if mc > 0 else fdv


def passes_low_mcap(row: Dict, mode: str = "balanced") -> bool:
    if is_major_symbol(str(row.get("symbol") or "")):
        return False

    cap = calc_cap(row)
    liq = float(row.get("liquidity_usd") or 0)
    vol = float(row.get("volume_24h") or 0)
    txns = float(row.get("txns_24h") or 0)

    cfg = {
        "safe": {"cap": 3_000_000, "liq": 25_000, "vol": 20_000, "txns": 120},
        "balanced": {"cap": 5_000_000, "liq": 10_000, "vol": 5_000, "txns": 50},
        "degen": {"cap": 8_000_000, "liq": 5_000, "vol": 2_500, "txns": 20},
    }[mode]

    return 0 < cap <= cfg["cap"] and liq >= cfg["liq"] and vol >= cfg["vol"] and txns >= cfg["txns"]


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
        if passes_low_mcap(r, mode=mode):
            out.append(r)
    return out
