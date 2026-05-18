# meme-heat-scanner

Low mcap meme coin candidate scanner built with Streamlit.

The app scans recent X posts, extracts contract addresses and cashtags, enriches candidates with DexScreener data, filters out unsuitable pairs, and ranks remaining candidates with a risk-adjusted `early_gem_score`.

## Features

- X Recent Search based candidate discovery
- EVM address, Solana address, and cashtag extraction
- DexScreener pair lookup
- Low market cap filtering by mode: `safe`, `balanced`, `degen`
- Major symbol exclusion for `BTC`, `ETH`, `SOL`, `USDT`, `USDC`, `BNB`, `DOGE`, `SHIB`, and `PEPE`
- Previously pumped token exclusion based on historical `max_seen_cap`
- Risk-adjusted `early_gem_score` with a final score cap
- Separate `risk_level`: `Low`, `Medium`, `High`, `Extreme`
- SQLite scan history and per-token registry
- Tabs for `Candidate Ranking`, `High Risk Alerts`, `Excluded`, and `Debug`
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

## Previously Pumped Filter

The app stores per-token historical highs in `token_registry`, keyed by `chain + token_address`.

Registry fields include:

- `chain`
- `token_address`
- `symbol`
- `name`
- `first_seen_at`
- `last_seen_at`
- `max_seen_cap`
- `max_seen_liquidity`
- `max_seen_volume_24h`

On every scan, DexScreener pairs are written to the registry before low-cap filtering. `max_seen_cap` uses `market_cap` when available, otherwise `fdv`.

The UI includes:

- `Exclude previously pumped tokens`, default ON
- `Previously pumped threshold`, default `2,000,000`

When enabled, rows with `max_seen_cap >= threshold` are removed from `Candidate Ranking` and marked with `previously_pumped_max_seen_cap` in `exclusion_reason`. They appear in the `Excluded` tab instead.

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
- `current_cap`
- `max_seen_cap`
- `first_seen_at`
- `last_seen_at`
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
