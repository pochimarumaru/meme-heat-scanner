# meme-heat-scanner

Low mcap meme coin candidate scanner built with Streamlit.

The app scans recent X posts, extracts contract addresses and cashtags, enriches candidates with DexScreener data, filters out unsuitable pairs, and ranks remaining candidates with a risk-adjusted `early_gem_score`.

## Features

- X Recent Search based candidate discovery
- EVM address, Solana address, and cashtag extraction
- DexScreener pair lookup
- Low market cap filtering by mode: `safe`, `balanced`, `degen`
- Major symbol exclusion for assets such as `SOL`, `ETH`, `BTC`, `USDT`, `USDC`, and `BNB`
- Risk-adjusted `early_gem_score`
- Separate `risk_level`: `Low`, `Medium`, `High`, `Extreme`
- SQLite scan history
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

`early_gem_score` is designed to avoid easy 100-point saturation. It uses capped log-scale scoring for discovery and market signals, then subtracts risk penalties.

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
- `x_engagement` is 0
- `volume_24h / liquidity_usd` is too high
- `price_change_24h` is extreme
- 2 or more `risk_flags` are present
- 3 or more `risk_flags` are present

Candidates with 3 or more `risk_flags` are capped to a low score so they fall toward the bottom of the ranking.

## Risk Levels

`risk_level` is displayed separately from score so degen-mode candidates can still be ranked while clearly showing risk.

- `Low`: no major risk flags and healthy X activity
- `Medium`: light risk, one mention, or no engagement
- `High`: multiple flags, high volume/liquidity ratio, or extreme price movement
- `Extreme`: 3 or more flags, extreme volume/liquidity ratio, very large price movement, or no sells detected

## CSV Export

The ranking table can be exported from the app with the `Export CSV` button. The exported CSV includes `risk_level` alongside the score and flags.

Key exported columns include:

- `symbol`
- `name`
- `chain`
- `cap`
- `fdv`
- `liquidity_usd`
- `volume_24h`
- `txns_24h`
- `x_mentions`
- `unique_authors`
- `x_engagement`
- `risk_level`
- `risk_flags`
- `early_gem_score`
- `url`

## Notes

This tool is for research and monitoring only. It is not financial advice.
