from typing import Any, Dict, List

import requests

BASE_URL = "https://api.dexscreener.com/latest/dex/search"


def _safe(data: Dict[str, Any], *keys: str, default=0):
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def search_pairs(term: str) -> List[Dict[str, Any]]:
    try:
        r = requests.get(BASE_URL, params={"q": term}, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return []

    rows = []
    for p in (r.json().get("pairs", []) or []):
        b = p.get("baseToken", {})
        rows.append(
            {
                "chain": p.get("chainId"),
                "dex_id": p.get("dexId"),
                "pair_address": p.get("pairAddress"),
                "token_address": b.get("address"),
                "symbol": b.get("symbol"),
                "name": b.get("name"),
                "price_usd": float(p.get("priceUsd") or 0),
                "fdv": float(p.get("fdv") or 0),
                "market_cap": float(p.get("marketCap") or 0),
                "liquidity_usd": float(_safe(p, "liquidity", "usd", default=0) or 0),
                "volume_24h": float(_safe(p, "volume", "h24", default=0) or 0),
                "volume_1h": float(_safe(p, "volume", "h1", default=0) or 0),
                "buys_24h": int(_safe(p, "txns", "h24", "buys", default=0) or 0),
                "sells_24h": int(_safe(p, "txns", "h24", "sells", default=0) or 0),
                "price_change_24h": float(_safe(p, "priceChange", "h24", default=0) or 0),
                "pair_created_at": p.get("pairCreatedAt"),
                "url": p.get("url"),
            }
        )

    for row in rows:
        row["txns_24h"] = row["buys_24h"] + row["sells_24h"]
    return rows
