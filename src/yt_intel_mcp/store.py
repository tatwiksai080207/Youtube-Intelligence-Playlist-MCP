"""Local WAL SQLite persistence store for quota, cache, and observation state (SR-10, ADR-0006)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from yt_intel_mcp.config import AppConfig

__all__ = ["CacheEntryKind", "CacheEntryRow", "QuotaLedgerRow", "SQLiteStore"]

CacheEntryKind = Literal["videos", "channels", "searches", "user_lists", "categories"]
_VALID_CACHE_KINDS: frozenset[str] = frozenset(
    {"videos", "channels", "searches", "user_lists", "categories"}
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS quota_ledger (
    budget_date TEXT PRIMARY KEY,
    units_used INTEGER NOT NULL DEFAULT 0 CHECK (units_used >= 0),
    search_calls_used INTEGER NOT NULL DEFAULT 0 CHECK (search_calls_used >= 0),
    upstream_exhausted INTEGER NOT NULL DEFAULT 0 CHECK (upstream_exhausted IN (0, 1)),
    exhausted_until_utc TEXT,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT PRIMARY KEY,
    entry_kind TEXT NOT NULL CHECK (
        entry_kind IN ('videos', 'channels', 'searches', 'user_lists', 'categories')
    ),
    is_personal INTEGER NOT NULL DEFAULT 0 CHECK (is_personal IN (0, 1)),
    payload_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    expires_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_entries_expires
    ON cache_entries (expires_at_utc);

CREATE INDEX IF NOT EXISTS idx_cache_entries_personal
    ON cache_entries (is_personal, entry_kind);

CREATE TABLE IF NOT EXISTS first_observed (
    source TEXT NOT NULL CHECK (
        source IN ('liked_video', 'subscription', 'playlist_item')
    ),
    item_id TEXT NOT NULL,
    first_observed_utc TEXT NOT NULL,
    PRIMARY KEY (source, item_id)
);
"""


@dataclass(frozen=True, slots=True)
class QuotaLedgerRow:
    """Persisted Pacific Time daily quota record in SQLite."""

    budget_date: str
    units_used: int
    search_calls_used: int
    upstream_exhausted: bool
    exhausted_until_utc: str | None
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class CacheEntryRow:
    """Persisted TTL metadata cache entry in SQLite."""

    cache_key: str
    entry_kind: CacheEntryKind
    is_personal: bool
    payload_json: str
    created_at_utc: str
    expires_at_utc: str


def _row_to_cache_entry(row: sqlite3.Row) -> CacheEntryRow:
    kind_raw = str(row["entry_kind"])
    if kind_raw not in _VALID_CACHE_KINDS:
        raise ValueError(f"Invalid stored cache entry_kind: {kind_raw!r}")
    return CacheEntryRow(
        cache_key=str(row["cache_key"]),
        entry_kind=cast(CacheEntryKind, kind_raw),
        is_personal=bool(row["is_personal"]),
        payload_json=str(row["payload_json"]),
        created_at_utc=str(row["created_at_utc"]),
        expires_at_utc=str(row["expires_at_utc"]),
    )


class SQLiteStore:
    """Transactional SQLite persistence layer running in WAL mode without storing secrets."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        config: AppConfig | None = None,
    ) -> None:
        base_config = config or AppConfig()
        self.db_path: Path = (
            Path(db_path) if db_path is not None else (base_config.data_dir / "yt_intel.db")
        )
        self.initialize()

    @classmethod
    def from_config(cls, config: AppConfig) -> SQLiteStore:
        """Create a SQLiteStore inside ``config.data_dir / 'yt_intel.db'``."""
        return cls(config.data_dir / "yt_intel.db", config=config)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        """Execute SQLite statements inside an explicit atomic transaction."""
        conn = self._connect()
        started = False
        try:
            conn.execute("BEGIN IMMEDIATE;" if immediate else "BEGIN;")
            started = True
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            if started and conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create schema tables and indices idempotently under WAL mode."""
        with self.transaction(immediate=True) as conn:
            for statement in _SCHEMA_SQL.strip().split(";"):
                cleaned = statement.strip()
                if cleaned:
                    conn.execute(cleaned)

    def journal_mode(self) -> str:
        """Return the active SQLite journal mode (expected `'wal'`)."""
        with self.transaction(immediate=False) as conn:
            row = conn.execute("PRAGMA journal_mode;").fetchone()
            return str(row[0]).lower() if row is not None else ""

    def read_quota_row(
        self,
        conn: sqlite3.Connection,
        budget_date: str,
    ) -> QuotaLedgerRow | None:
        """Fetch a quota row for ``budget_date`` inside an active transaction."""
        row = conn.execute(
            """
            SELECT
                budget_date,
                units_used,
                search_calls_used,
                upstream_exhausted,
                exhausted_until_utc,
                updated_at_utc
            FROM quota_ledger
            WHERE budget_date = ?;
            """,
            (budget_date,),
        ).fetchone()
        if row is None:
            return None
        return QuotaLedgerRow(
            budget_date=str(row["budget_date"]),
            units_used=int(row["units_used"]),
            search_calls_used=int(row["search_calls_used"]),
            upstream_exhausted=bool(row["upstream_exhausted"]),
            exhausted_until_utc=(
                str(row["exhausted_until_utc"]) if row["exhausted_until_utc"] is not None else None
            ),
            updated_at_utc=str(row["updated_at_utc"]),
        )

    def get_quota_row(self, budget_date: str) -> QuotaLedgerRow | None:
        """Read a committed quota ledger row outside a caller managed transaction."""
        with self.transaction(immediate=False) as conn:
            return self.read_quota_row(conn, budget_date)

    def add_quota_usage(
        self,
        conn: sqlite3.Connection,
        budget_date: str,
        *,
        units: int,
        search_calls: int,
        updated_at_utc: str,
    ) -> QuotaLedgerRow:
        """Atomically increment daily unit and search call counters for ``budget_date``."""
        conn.execute(
            """
            INSERT INTO quota_ledger (
                budget_date,
                units_used,
                search_calls_used,
                upstream_exhausted,
                exhausted_until_utc,
                updated_at_utc
            ) VALUES (?, ?, ?, 0, NULL, ?)
            ON CONFLICT(budget_date) DO UPDATE SET
                units_used = quota_ledger.units_used + excluded.units_used,
                search_calls_used = quota_ledger.search_calls_used + excluded.search_calls_used,
                updated_at_utc = excluded.updated_at_utc;
            """,
            (budget_date, units, search_calls, updated_at_utc),
        )
        updated = self.read_quota_row(conn, budget_date)
        assert updated is not None
        return updated

    def set_quota_upstream_exhausted(
        self,
        conn: sqlite3.Connection,
        budget_date: str,
        *,
        exhausted_until_utc: str,
        updated_at_utc: str,
    ) -> QuotaLedgerRow:
        """Mark upstream quota exhausted until ``exhausted_until_utc`` for ``budget_date``."""
        conn.execute(
            """
            INSERT INTO quota_ledger (
                budget_date,
                units_used,
                search_calls_used,
                upstream_exhausted,
                exhausted_until_utc,
                updated_at_utc
            ) VALUES (?, 0, 0, 1, ?, ?)
            ON CONFLICT(budget_date) DO UPDATE SET
                upstream_exhausted = 1,
                exhausted_until_utc = excluded.exhausted_until_utc,
                updated_at_utc = excluded.updated_at_utc;
            """,
            (budget_date, exhausted_until_utc, updated_at_utc),
        )
        updated = self.read_quota_row(conn, budget_date)
        assert updated is not None
        return updated

    def purge_personal_data(self) -> tuple[int, int]:
        """Delete personal cached lists and first_observed rows while preserving quota_ledger."""
        with self.transaction(immediate=True) as conn:
            cache_cursor = conn.execute(
                "DELETE FROM cache_entries WHERE is_personal = 1 OR entry_kind = 'user_lists';"
            )
            observed_cursor = conn.execute("DELETE FROM first_observed;")
            return (max(cache_cursor.rowcount, 0), max(observed_cursor.rowcount, 0))

    def read_cache_entry(
        self,
        conn: sqlite3.Connection,
        cache_key: str,
    ) -> CacheEntryRow | None:
        """Fetch a single cache entry inside an active transaction."""
        row = conn.execute(
            """
            SELECT
                cache_key,
                entry_kind,
                is_personal,
                payload_json,
                created_at_utc,
                expires_at_utc
            FROM cache_entries
            WHERE cache_key = ?;
            """,
            (cache_key,),
        ).fetchone()
        return _row_to_cache_entry(row) if row is not None else None

    def read_cache_entries(
        self,
        conn: sqlite3.Connection,
        cache_keys: list[str] | tuple[str, ...],
    ) -> dict[str, CacheEntryRow]:
        """Batch fetch cache entries by key inside an active transaction."""
        unique_keys = list(dict.fromkeys(cache_keys))
        if not unique_keys:
            return {}
        placeholders = ",".join("?" for _ in unique_keys)
        rows = conn.execute(
            f"""
            SELECT
                cache_key,
                entry_kind,
                is_personal,
                payload_json,
                created_at_utc,
                expires_at_utc
            FROM cache_entries
            WHERE cache_key IN ({placeholders});
            """,
            unique_keys,
        ).fetchall()
        result: dict[str, CacheEntryRow] = {}
        for row in rows:
            entry = _row_to_cache_entry(row)
            result[entry.cache_key] = entry
        return result

    def get_cache_entry(self, cache_key: str) -> CacheEntryRow | None:
        """Read a committed cache row outside a caller managed transaction."""
        with self.transaction(immediate=False) as conn:
            return self.read_cache_entry(conn, cache_key)

    def upsert_cache_entry(
        self,
        conn: sqlite3.Connection,
        *,
        cache_key: str,
        entry_kind: CacheEntryKind,
        is_personal: bool,
        payload_json: str,
        created_at_utc: str,
        expires_at_utc: str,
    ) -> CacheEntryRow:
        """Insert or replace a cache entry inside an active transaction."""
        conn.execute(
            """
            INSERT INTO cache_entries (
                cache_key,
                entry_kind,
                is_personal,
                payload_json,
                created_at_utc,
                expires_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                entry_kind = excluded.entry_kind,
                is_personal = excluded.is_personal,
                payload_json = excluded.payload_json,
                created_at_utc = excluded.created_at_utc,
                expires_at_utc = excluded.expires_at_utc;
            """,
            (
                cache_key,
                entry_kind,
                int(is_personal),
                payload_json,
                created_at_utc,
                expires_at_utc,
            ),
        )
        stored = self.read_cache_entry(conn, cache_key)
        assert stored is not None
        return stored

    def delete_cache_entry(self, conn: sqlite3.Connection, cache_key: str) -> bool:
        """Delete a single cache entry inside an active transaction."""
        cursor = conn.execute("DELETE FROM cache_entries WHERE cache_key = ?;", (cache_key,))
        return cursor.rowcount > 0

    def delete_cache_entries_by_prefix(self, conn: sqlite3.Connection, prefix: str) -> int:
        """Delete cache entries whose key starts with ``prefix`` inside a transaction."""
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        cursor = conn.execute(
            "DELETE FROM cache_entries WHERE cache_key LIKE ? ESCAPE '\\';",
            (f"{escaped}%",),
        )
        return max(cursor.rowcount, 0)

    def delete_expired_cache_entries(self, conn: sqlite3.Connection, *, now_utc_iso: str) -> int:
        """Delete all cache entries with ``expires_at_utc <= now_utc_iso``."""
        cursor = conn.execute(
            "DELETE FROM cache_entries WHERE expires_at_utc <= ?;",
            (now_utc_iso,),
        )
        return max(cursor.rowcount, 0)
