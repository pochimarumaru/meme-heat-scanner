# meme-heat-scanner

Low mcap meme coin candidate scanner built with Streamlit.

The app scans recent X posts, extracts contract addresses and cashtags, enriches candidates with DexScreener data, filters out unsuitable pairs, and ranks remaining candidates with a risk-adjusted `early_gem_score`.

## Features

- X Recent Search based candidate discovery
- EVM address, Solana address, and cashtag extraction
- DexScreener pair lookup
- Low market cap filtering by mode: `safe`, `balanced`, `degen`
- Major symbol exclusion for `BTC`, `ETH`, `SOL`, `USDT`, `USDC`, `BNB`, `DOGE`, `SHIB`, and `PEPE`
- Risk-adjusted `early_gem_score` with a final score cap
- Separate `risk_level`: `Low`, `Medium`, `High`, `Extreme`
- SQLite scan history
- Tabs for `Candidate Ranking`, `High Risk Alerts`, and `Debug`
- Ranking table, history charts, and CSV export

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file and set your X API bearer token:

```bash
X_BEARER_TOKEN=your_bearer_token_here
```

Run the app:

```bash
streamlit run app.py
```

## Scoring

`early_gem_score` is designed to avoid easy 100-point saturation. It uses capped log-scale scoring for discovery and market signals, subtracts risk penalties, then applies a final cap.

Positive signals include:

- `x_mentions`
- `unique_authors`
- `x_engagement`
- `ca_mentions`
- `volume_24h`
- `volume_1h`
- `txns_24h`
- `liquidity_usd`
- low FDV / market cap quality

Large penalties are applied when:

- `x_mentions` is only 1
- `unique_authors` is 1 or less
- `x_engagement` is 0
- `volume_24h / liquidity_usd` is too high
- `price_change_24h` is extreme
- `risk_level` is `High`
- `risk_level` is `Extreme`

`Extreme` risk candidates are limited to a 0-20 score range.

## Risk Levels

`risk_level` is derived from `risk_flags` so it does not fall back to `Unknown`.

- `Low`: 0 risk flags
- `Medium`: 1 risk flag
- `High`: 2 risk flags, or `no_sells_detected`
- `Extreme`: 3 or more risk flags, or `volume_liquidity_ratio_extreme`

## CSV Export

The ranking table can be exported from the app with the `Export CSV` button. The exported CSV includes risk, debug, and score explanation fields.

Key exported columns include:

- `symbol`
- `name`
- `chain`
- `cap`
- `fdv`
- `liquidity_usd`
- `volume_24h`
- `volume_liquidity_ratio`
- `txns_24h`
- `x_mentions`
- `unique_authors`
- `x_engagement`
- `risk_level`
- `flag_count`
- `risk_flags`
- `exclusion_reason`
- `early_gem_score`
- `score_breakdown`
- `url`

## Notes

This tool is for research and monitoring only. It is not financial advice.
