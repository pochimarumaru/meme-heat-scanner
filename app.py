from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from db import init_db, insert_scan, read_history, read_latest_rankings
from dexscreener_lookup import search_pairs
from early_score import compute_score_details
from low_mcap_filter import exclusion_reason, filter_candidates
from x_monitor import extract_candidates, fetch_recent_tweets, term_signals

st.set_page_config(page_title="Low Mcap Meme Scanner", layout="wide")
st.title("Low Mcap Meme Coin Candidate Scanner")
st.caption("X Recent Search + Contract/Cashtag extraction + DexScreener lookup")

init_db()

mode = st.selectbox("Mode", ["safe", "balanced", "degen"], index=1)
max_tweets = st.slider("Tweets to scan", min_value=20, max_value=100, value=50, step=10)

EXPORT_COLUMNS = [
    "symbol",
    "name",
    "chain",
    "cap",
    "fdv",
    "liquidity_usd",
    "volume_24h",
    "volume_liquidity_ratio",
    "txns_24h",
    "x_mentions",
    "unique_authors",
    "x_engagement",
    "risk_level",
    "flag_count",
    "risk_flags",
    "exclusion_reason",
    "early_gem_score",
    "score_breakdown",
    "url",
]

RANKING_COLUMNS = [
    "symbol",
    "name",
    "chain",
    "cap",
    "liquidity_usd",
    "volume_24h",
    "volume_liquidity_ratio",
    "txns_24h",
    "x_mentions",
    "unique_authors",
    "x_engagement",
    "risk_level",
    "flag_count",
    "risk_flags",
    "early_gem_score",
    "url",
]


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
        details = compute_score_details({**row, **x_signals})
        payload = {
            "scanned_at": now,
            "mode": selected_mode,
            "tweet_count": len(tweets),
            **row,
            **x_signals,
            "unique_authors": details["unique_authors"],
            "early_gem_score": details["early_gem_score"],
            "risk_flags": ",".join(details["risk_flags"]),
            "risk_level": details["risk_level"],
            "volume_liquidity_ratio": details["volume_liquidity_ratio"],
            "flag_count": details["flag_count"],
            "exclusion_reason": row.get("exclusion_reason", ""),
            "score_breakdown": details["score_breakdown"],
        }
        insert_scan(payload)
        inserted += 1
    return inserted


def _ensure_numeric(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        df[column] = 0.0
    df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def prepare_rankings(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    for column in ["x_mentions", "unique_tweets", "unique_authors", "x_engagement"]:
        _ensure_numeric(df, column)
    df.loc[df["unique_authors"] <= 0, "unique_authors"] = df.loc[df["unique_authors"] <= 0, "unique_tweets"]
    df.loc[df["unique_authors"] <= 0, "unique_authors"] = df.loc[df["unique_authors"] <= 0, "x_mentions"]

    for column in ["risk_flags", "risk_level", "exclusion_reason", "score_breakdown"]:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].fillna("").astype(str)

    recalculated = df.apply(lambda row: compute_score_details(row.to_dict()), axis=1)
    df["early_gem_score"] = recalculated.apply(lambda x: x["early_gem_score"])
    df["risk_flags"] = recalculated.apply(lambda x: ",".join(x["risk_flags"]))
    df["risk_level"] = recalculated.apply(lambda x: x["risk_level"])
    df["volume_liquidity_ratio"] = recalculated.apply(lambda x: x["volume_liquidity_ratio"])
    df["flag_count"] = recalculated.apply(lambda x: x["flag_count"])
    df["score_breakdown"] = recalculated.apply(lambda x: x["score_breakdown"])
    df["unique_authors"] = recalculated.apply(lambda x: x["unique_authors"])
    df["exclusion_reason"] = df.apply(
        lambda row: row["exclusion_reason"] or exclusion_reason(row.to_dict()),
        axis=1,
    )
    df = df.sort_values(["early_gem_score", "x_mentions", "unique_authors"], ascending=[False, False, False])
    return df


def _select_columns(df: pd.DataFrame, columns) -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns].copy()


if st.button("Scan X now", type="primary"):
    with st.spinner("Scanning X and enriching with DexScreener..."):
        n = run_scan(mode, max_tweets)
    st.success(f"Scan done. Inserted {n} candidates.")

ranking = prepare_rankings(read_latest_rankings(limit=1000))
candidate_tab, alerts_tab, debug_tab = st.tabs(["Candidate Ranking", "High Risk Alerts", "Debug"])

with candidate_tab:
    st.subheader("Candidate Ranking")
    if ranking.empty:
        st.info("No data yet. Press 'Scan X now'. If empty persists, set X_BEARER_TOKEN in .env.")
    else:
        candidates = ranking[ranking["exclusion_reason"] == ""].copy()
        view = _select_columns(candidates, RANKING_COLUMNS)
        export_view = _select_columns(candidates, EXPORT_COLUMNS)
        st.dataframe(view, use_container_width=True)
        st.download_button(
            "Export CSV",
            data=export_view.to_csv(index=False).encode("utf-8-sig"),
            file_name="meme_heat_rankings.csv",
            mime="text/csv",
        )

        symbols = candidates["symbol"].dropna().unique().tolist()
        if symbols:
            selected = st.selectbox("Chart symbol", symbols, index=0)
            hist = prepare_rankings(read_history(selected))
            if not hist.empty:
                hist["scanned_at"] = pd.to_datetime(hist["scanned_at"])
                hist = hist.sort_values("scanned_at")
                fig1 = px.line(hist, x="scanned_at", y=["volume_24h", "liquidity_usd", "x_mentions"], markers=True)
                st.plotly_chart(fig1, use_container_width=True)
                fig2 = px.line(hist, x="scanned_at", y=["early_gem_score"], markers=True)
                st.plotly_chart(fig2, use_container_width=True)

with alerts_tab:
    st.subheader("High Risk Alerts")
    if ranking.empty:
        st.info("No data yet.")
    else:
        alerts = ranking[
            (ranking["exclusion_reason"] == "")
            & ((ranking["risk_level"].isin(["High", "Extreme"])) | (ranking["flag_count"] >= 2))
        ].copy()
        alerts["_risk_order"] = alerts["risk_level"].map({"Extreme": 0, "High": 1, "Medium": 2, "Low": 3}).fillna(9)
        alerts = alerts.sort_values(["_risk_order", "flag_count", "volume_liquidity_ratio"], ascending=[True, False, False])
        st.dataframe(_select_columns(alerts.drop(columns=["_risk_order"], errors="ignore"), RANKING_COLUMNS), use_container_width=True)

with debug_tab:
    st.subheader("Debug")
    if ranking.empty:
        st.info("No data yet.")
    else:
        debug_columns = EXPORT_COLUMNS + ["source_term", "tweet_count", "scanned_at", "pair_address", "token_address"]
        st.dataframe(_select_columns(ranking, debug_columns), use_container_width=True)

st.warning("Not financial advice.")
