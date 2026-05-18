import sqlite3
from typing import Optional

import pandas as pd

DB_PATH = "meme_heat.db"


def conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path, check_same_thread=False)


def _ensure_column(c: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


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
            score_breakdown TEXT
        )
        """
    )
    _ensure_column(c, "scans", "unique_authors", "REAL")
    _ensure_column(c, "scans", "risk_level", "TEXT")
    _ensure_column(c, "scans", "volume_liquidity_ratio", "REAL")
    _ensure_column(c, "scans", "flag_count", "INTEGER")
    _ensure_column(c, "scans", "exclusion_reason", "TEXT")
    _ensure_column(c, "scans", "score_breakdown", "TEXT")
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
          SELECT *, ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY scanned_at DESC, id DESC) rn
          FROM scans
          WHERE symbol IS NOT NULL AND symbol != ''
        )
        SELECT * FROM latest WHERE rn=1
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
        df = pd.read_sql_query("SELECT * FROM scans WHERE symbol=? ORDER BY scanned_at ASC", c, params=[symbol])
    else:
        df = pd.read_sql_query("SELECT * FROM scans ORDER BY scanned_at ASC", c)
    c.close()
    return df
