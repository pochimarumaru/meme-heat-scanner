import sqlite3
from typing import Iterable, Optional

import pandas as pd

DB_PATH = "meme_heat.db"


def conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path, check_same_thread=False)


def _ensure_column(c: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _calc_cap(row: dict) -> float:
    market_cap = float(row.get("market_cap") or 0)
    fdv = float(row.get("fdv") or 0)
    return market_cap if market_cap > 0 else fdv


def _backfill_token_registry(c: sqlite3.Connection) -> None:
    c.execute(
        """
        INSERT INTO token_registry (
            chain,
            token_address,
            symbol,
            name,
            first_seen_at,
            last_seen_at,
            max_seen_cap,
            max_seen_liquidity,
            max_seen_volume_24h
        )
        SELECT
            chain,
            token_address,
            MAX(symbol),
            MAX(name),
            MIN(scanned_at),
            MAX(scanned_at),
            MAX(COALESCE(NULLIF(cap, 0), NULLIF(market_cap, 0), fdv, 0)),
            MAX(COALESCE(liquidity_usd, 0)),
            MAX(COALESCE(volume_24h, 0))
        FROM scans
        WHERE chain IS NOT NULL
          AND chain != ''
          AND token_address IS NOT NULL
          AND token_address != ''
        GROUP BY chain, token_address
        ON CONFLICT(chain, token_address) DO UPDATE SET
            first_seen_at = MIN(token_registry.first_seen_at, excluded.first_seen_at),
            last_seen_at = MAX(token_registry.last_seen_at, excluded.last_seen_at),
            max_seen_cap = MAX(COALESCE(token_registry.max_seen_cap, 0), COALESCE(excluded.max_seen_cap, 0)),
            max_seen_liquidity = MAX(COALESCE(token_registry.max_seen_liquidity, 0), COALESCE(excluded.max_seen_liquidity, 0)),
            max_seen_volume_24h = MAX(COALESCE(token_registry.max_seen_volume_24h, 0), COALESCE(excluded.max_seen_volume_24h, 0))
        """
    )


def init_db(db_path: str = DB_PATH) -> None:
    c = conn(db_path)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT,
            mode TEXT,
            source_term TEXT,
            tweet_count INTEGER,
            chain TEXT,
            dex_id TEXT,
            pair_address TEXT,
            token_address TEXT,
            symbol TEXT,
            name TEXT,
            price_usd REAL,
            fdv REAL,
            market_cap REAL,
            cap REAL,
            liquidity_usd REAL,
            volume_24h REAL,
            volume_1h REAL,
            txns_24h REAL,
            buys_24h REAL,
            sells_24h REAL,
            price_change_24h REAL,
            pair_created_at TEXT,
            url TEXT,
            x_mentions REAL,
            x_engagement REAL,
            unique_tweets REAL,
            unique_authors REAL,
            ca_mentions REAL,
            early_gem_score REAL,
            risk_flags TEXT,
            risk_level TEXT,
            volume_liquidity_ratio REAL,
            flag_count INTEGER,
            exclusion_reason TEXT,
            current_cap_filter_pass INTEGER,
            history_saved INTEGER,
            near_previously_pumped INTEGER,
            score_breakdown TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS token_registry (
            chain TEXT NOT NULL,
            token_address TEXT NOT NULL,
            symbol TEXT,
            name TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            max_seen_cap REAL,
            max_seen_liquidity REAL,
            max_seen_volume_24h REAL,
            PRIMARY KEY (chain, token_address)
        )
        """
    )
    _ensure_column(c, "scans", "unique_authors", "REAL")
    _ensure_column(c, "scans", "risk_level", "TEXT")
    _ensure_column(c, "scans", "volume_liquidity_ratio", "REAL")
    _ensure_column(c, "scans", "flag_count", "INTEGER")
    _ensure_column(c, "scans", "exclusion_reason", "TEXT")
    _ensure_column(c, "scans", "current_cap_filter_pass", "INTEGER")
    _ensure_column(c, "scans", "history_saved", "INTEGER")
    _ensure_column(c, "scans", "near_previously_pumped", "INTEGER")
    _ensure_column(c, "scans", "score_breakdown", "TEXT")
    _backfill_token_registry(c)
    c.commit()
    c.close()


def update_token_registry(row: dict, seen_at: str, db_path: str = DB_PATH) -> None:
    chain = str(row.get("chain") or "").strip()
    token_address = str(row.get("token_address") or "").strip()
    if not chain or not token_address:
        return

    payload = {
        "chain": chain,
        "token_address": token_address,
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "first_seen_at": seen_at,
        "last_seen_at": seen_at,
        "max_seen_cap": _calc_cap(row),
        "max_seen_liquidity": float(row.get("liquidity_usd") or 0),
        "max_seen_volume_24h": float(row.get("volume_24h") or 0),
    }
    c = conn(db_path)
    c.execute(
        """
        INSERT INTO token_registry (
            chain,
            token_address,
            symbol,
            name,
            first_seen_at,
            last_seen_at,
            max_seen_cap,
            max_seen_liquidity,
            max_seen_volume_24h
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chain, token_address) DO UPDATE SET
            symbol = excluded.symbol,
            name = excluded.name,
            last_seen_at = excluded.last_seen_at,
            max_seen_cap = MAX(COALESCE(token_registry.max_seen_cap, 0), COALESCE(excluded.max_seen_cap, 0)),
            max_seen_liquidity = MAX(COALESCE(token_registry.max_seen_liquidity, 0), COALESCE(excluded.max_seen_liquidity, 0)),
            max_seen_volume_24h = MAX(COALESCE(token_registry.max_seen_volume_24h, 0), COALESCE(excluded.max_seen_volume_24h, 0))
        """,
        [
            payload["chain"],
            payload["token_address"],
            payload["symbol"],
            payload["name"],
            payload["first_seen_at"],
            payload["last_seen_at"],
            payload["max_seen_cap"],
            payload["max_seen_liquidity"],
            payload["max_seen_volume_24h"],
        ],
    )
    c.commit()
    c.close()


def update_token_registry_many(rows: Iterable[dict], seen_at: str, db_path: str = DB_PATH) -> None:
    c = conn(db_path)
    for row in rows:
        chain = str(row.get("chain") or "").strip()
        token_address = str(row.get("token_address") or "").strip()
        if not chain or not token_address:
            continue
        c.execute(
            """
            INSERT INTO token_registry (
                chain,
                token_address,
                symbol,
                name,
                first_seen_at,
                last_seen_at,
                max_seen_cap,
                max_seen_liquidity,
                max_seen_volume_24h
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chain, token_address) DO UPDATE SET
                symbol = excluded.symbol,
                name = excluded.name,
                last_seen_at = excluded.last_seen_at,
                max_seen_cap = MAX(COALESCE(token_registry.max_seen_cap, 0), COALESCE(excluded.max_seen_cap, 0)),
                max_seen_liquidity = MAX(COALESCE(token_registry.max_seen_liquidity, 0), COALESCE(excluded.max_seen_liquidity, 0)),
                max_seen_volume_24h = MAX(COALESCE(token_registry.max_seen_volume_24h, 0), COALESCE(excluded.max_seen_volume_24h, 0))
            """,
            [
                chain,
                token_address,
                row.get("symbol"),
                row.get("name"),
                seen_at,
                seen_at,
                _calc_cap(row),
                float(row.get("liquidity_usd") or 0),
                float(row.get("volume_24h") or 0),
            ],
        )
    c.commit()
    c.close()


def insert_scan(row: dict, db_path: str = DB_PATH) -> None:
    c = conn(db_path)
    keys = list(row.keys())
    c.execute(
        f"INSERT INTO scans ({','.join(keys)}) VALUES ({','.join(['?'] * len(keys))})",
        [row[k] for k in keys],
    )
    c.commit()
    c.close()


def read_latest_rankings(limit: int = 100, db_path: str = DB_PATH) -> pd.DataFrame:
    c = conn(db_path)
    df = pd.read_sql_query(
        """
        WITH latest AS (
          SELECT
            *,
            ROW_NUMBER() OVER(
              PARTITION BY COALESCE(NULLIF(chain, '') || ':' || NULLIF(token_address, ''), symbol)
              ORDER BY scanned_at DESC, id DESC
            ) rn
          FROM scans
          WHERE symbol IS NOT NULL AND symbol != ''
        )
        SELECT
          latest.*,
          latest.cap AS current_cap,
          COALESCE(token_registry.max_seen_cap, latest.cap) AS max_seen_cap,
          COALESCE(token_registry.max_seen_liquidity, latest.liquidity_usd) AS max_seen_liquidity,
          COALESCE(token_registry.max_seen_volume_24h, latest.volume_24h) AS max_seen_volume_24h,
          token_registry.first_seen_at AS first_seen_at,
          token_registry.last_seen_at AS last_seen_at
        FROM latest
        LEFT JOIN token_registry
          ON latest.chain = token_registry.chain
         AND latest.token_address = token_registry.token_address
        WHERE rn=1
        ORDER BY scanned_at DESC, id DESC
        LIMIT ?
        """,
        c,
        params=[limit],
    )
    c.close()
    return df


def read_history(symbol: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    c = conn(db_path)
    if symbol:
        df = pd.read_sql_query(
            """
            SELECT
              scans.*,
              scans.cap AS current_cap,
              COALESCE(token_registry.max_seen_cap, scans.cap) AS max_seen_cap,
              COALESCE(token_registry.max_seen_liquidity, scans.liquidity_usd) AS max_seen_liquidity,
              COALESCE(token_registry.max_seen_volume_24h, scans.volume_24h) AS max_seen_volume_24h,
              token_registry.first_seen_at AS first_seen_at,
              token_registry.last_seen_at AS last_seen_at
            FROM scans
            LEFT JOIN token_registry
              ON scans.chain = token_registry.chain
             AND scans.token_address = token_registry.token_address
            WHERE scans.symbol=?
            ORDER BY scans.scanned_at ASC
            """,
            c,
            params=[symbol],
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT
              scans.*,
              scans.cap AS current_cap,
              COALESCE(token_registry.max_seen_cap, scans.cap) AS max_seen_cap,
              COALESCE(token_registry.max_seen_liquidity, scans.liquidity_usd) AS max_seen_liquidity,
              COALESCE(token_registry.max_seen_volume_24h, scans.volume_24h) AS max_seen_volume_24h,
              token_registry.first_seen_at AS first_seen_at,
              token_registry.last_seen_at AS last_seen_at
            FROM scans
            LEFT JOIN token_registry
              ON scans.chain = token_registry.chain
             AND scans.token_address = token_registry.token_address
            ORDER BY scans.scanned_at ASC
            """,
            c,
        )
    c.close()
    return df
