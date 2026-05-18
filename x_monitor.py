import os
import re
from collections import Counter
from typing import Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()

X_ENDPOINT = "https://api.x.com/2/tweets/search/recent"
EVM_RE = re.compile(r"0x[a-fA-F0-9]{40}")
SOL_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
CASHTAG_RE = re.compile(r"\$[A-Za-z][A-Za-z0-9_]{1,14}")


def build_query() -> str:
    keywords = [
        '"low mcap"', '"new gem"', '"just launched"', '"stealth launch"',
        '"fair launch"', 'pumpfun', 'dexscreener', '"contract address"', '"ca:"',
    ]
    return "(" + " OR ".join(keywords) + ") -is:retweet lang:en"


def fetch_recent_tweets(max_results: int = 50) -> List[Dict]:
    bearer = os.getenv("X_BEARER_TOKEN", "")
    if not bearer:
        return []
    params = {
        "query": build_query(),
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at,public_metrics,author_id,lang",
        "expansions": "author_id",
        "user.fields": "username,public_metrics,verified",
    }
    try:
        r = requests.get(
            X_ENDPOINT,
            headers={"Authorization": f"Bearer {bearer}"},
            params=params,
            timeout=20,
        )
        r.raise_for_status()
    except requests.RequestException:
        return []

    payload = r.json()
    users = {u["id"]: u for u in payload.get("includes", {}).get("users", [])}
    rows: List[Dict] = []
    for tw in payload.get("data", []) or []:
        metrics = tw.get("public_metrics", {})
        author = users.get(tw.get("author_id", ""), {})
        rows.append(
            {
                "tweet_id": tw.get("id"),
                "created_at": tw.get("created_at"),
                "author_id": tw.get("author_id"),
                "username": author.get("username"),
                "verified": bool(author.get("verified", False)),
                "lang": tw.get("lang"),
                "text": tw.get("text", ""),
                "like_count": int(metrics.get("like_count", 0)),
                "retweet_count": int(metrics.get("retweet_count", 0)),
                "reply_count": int(metrics.get("reply_count", 0)),
                "quote_count": int(metrics.get("quote_count", 0)),
            }
        )
    return rows


def extract_candidates(tweets: List[Dict]) -> Dict[str, List[str]]:
    evm, sol, tags = [], [], []
    for t in tweets:
        text = t.get("text", "")
        evm.extend(EVM_RE.findall(text))
        sol.extend([x for x in SOL_RE.findall(text) if not x.startswith("0x")])
        tags.extend(CASHTAG_RE.findall(text))
    return {
        "evm_addresses": list(Counter(evm).keys()),
        "sol_addresses": list(Counter(sol).keys()),
        "cashtags": list(Counter(tags).keys()),
    }


def aggregate_x_signals(tweets: List[Dict]) -> Dict[str, float]:
    unique = {t.get("tweet_id") for t in tweets if t.get("tweet_id")}
    unique_authors = {t.get("author_id") or t.get("username") for t in tweets if t.get("author_id") or t.get("username")}
    engagement = sum(
        t.get("like_count", 0) + t.get("retweet_count", 0) + t.get("reply_count", 0) + t.get("quote_count", 0)
        for t in tweets
    )
    ca_mentions = sum(
        1 for t in tweets
        if EVM_RE.search(t.get("text", "")) or SOL_RE.search(t.get("text", "")) or "ca:" in t.get("text", "").lower()
    )
    return {
        "x_mentions": float(len(tweets)),
        "x_engagement": float(engagement),
        "unique_tweets": float(len(unique)),
        "unique_authors": float(len(unique_authors)),
        "ca_mentions": float(ca_mentions),
    }


def term_signals(tweets: List[Dict], term: str) -> Dict[str, float]:
    needle = term.lower()
    related = [t for t in tweets if needle and needle in t.get("text", "").lower()]
    if not related:
        return {
            "x_mentions": 0.0,
            "x_engagement": 0.0,
            "unique_tweets": 0.0,
            "unique_authors": 0.0,
            "ca_mentions": 0.0,
        }
    return aggregate_x_signals(related)
