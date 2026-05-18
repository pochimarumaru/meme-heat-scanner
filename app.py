from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from db import init_db, insert_scan, read_history, read_latest_rankings
from dexscreener_lookup import search_pairs
from early_score import compute_early_gem_score, compute_risk_level
from low_mcap_filter import filter_candidates
from x_monitor import extract_candidates, fetch_recent_tweets, term_signals

st.set_page_config(page_title="Low Mcap Meme Scanner", layout="wide")
st.title("Low Mcap Meme Coin Candidate Scanner")
st.caption("X Recent Search + Contract/Cashtag extraction + DexScreener lookup")

init_db()

mode = st.selectbox("Mode", ["safe", "balanced", "degen"], index=1)
max_tweets = st.slider("Tweets to scan", min_value=20, max_value=100, value=50, step=10)


def run_scan(selected_mode: str, tweet_size: int) -> int:
    tweets = fetch_recent_tweets(max_results=tweet_size)
    candidates = extract_candidates(tweets)

    terms = []
    terms.extend(candidates["evm_addresses"])
    terms.extend(candidates["sol_addresses"])
    terms.extend([c.replace("$", "") for c in candidates["cashtags"]])
    terms = list(dict.fromkeys(terms))[:80]

    all_pairs = []
    for term in terms:
        for pair in search_pairs(term):
            row = dict(pair)
            row["source_term"] = term
            all_pairs.append(row)

    filtered = filter_candidates(all_pairs, mode=selected_mode)
    now = datetime.now(timezone.utc).isoformat()

    inserted = 0
    for row in filtered:
        x_signals = term_signals(tweets, row.get("source_term", ""))
        score, _, flags = compute_early_gem_score({**row, **x_signals})
        risk_level = compute_risk_level({**row, **x_signals}, flags)
        payload = {
            "scanned_at": now,
            "mode": selected_mode,
            "tweet_count": len(tweets),
            **row,
            **x_signals,
            "early_gem_score": score,
            "risk_flags": ",".join(flags),
            "risk_level": risk_level,
        }
        insert_scan(payload)
        inserted += 1
    return inserted


if st.button("Scan X now", type="primary"):
    with st.spinner("Scanning X and enriching with DexScreener..."):
        n = run_scan(mode, max_tweets)
    st.success(f"Scan done. Inserted {n} candidates.")

ranking = read_latest_rankings(limit=200)
st.subheader("Early Gem Ranking")
if ranking.empty:
    st.info("No data yet. Press 'Scan X now'. If empty persists, set X_BEARER_TOKEN in .env.")
else:
    if "risk_level" not in ranking.columns:
        ranking["risk_level"] = "Unknown"
    ranking["risk_level"] = ranking["risk_level"].fillna("Unknown")

    view = ranking[
        [
            "symbol",
            "name",
            "chain",
            "cap",
            "fdv",
            "liquidity_usd",
            "volume_24h",
            "txns_24h",
            "x_mentions",
            "unique_authors",
            "x_engagement",
            "risk_level",
            "risk_flags",
            "early_gem_score",
            "url",
        ]
    ].copy()
    st.dataframe(view, use_container_width=True)
    st.download_button(
        "Export CSV",
        data=view.to_csv(index=False).encode("utf-8-sig"),
        file_name="meme_heat_rankings.csv",
        mime="text/csv",
    )

    symbols = ranking["symbol"].dropna().unique().tolist()
    if symbols:
        selected = st.selectbox("Chart symbol", symbols, index=0)
        hist = read_history(selected)
        if not hist.empty:
            hist["scanned_at"] = pd.to_datetime(hist["scanned_at"])
            fig1 = px.line(hist, x="scanned_at", y=["volume_24h", "liquidity_usd", "x_mentions"], markers=True)
            st.plotly_chart(fig1, use_container_width=True)
            fig2 = px.line(hist, x="scanned_at", y=["early_gem_score"], markers=True)
            st.plotly_chart(fig2, use_container_width=True)

st.warning("Not financial advice.")
