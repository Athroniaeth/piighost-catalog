"""How the catalog is used, counted rather than logged.

The site promises that a text sent to the playground is never written to a
database. Analytics that broke that promise would be worse than no analytics, so
this is not a request log with the fields trimmed off. It is a table of counters,
and the difference is structural rather than a matter of discipline:

- The finest resolution is the hour. There is no row that corresponds to one
  request, so there is nothing to correlate.
- The only columns are the shape of the call: what kind it was, which registry
  object it named, whether the reference was pinned, whether the caller was a
  browser or the library, and the status. No address, no user agent string, no
  session, no body, ever.
- Writes are `INSERT ... ON CONFLICT DO UPDATE SET count = count + 1`, so two
  identical calls in the same hour are indistinguishable by construction.

What it answers is the question that prompted it: which configurations does the
piighost library actually pull, through a `catalog:` reference in a pipeline
config or `RegexDetector.from_catalog`, pinned or floating, and does that change
over time. What it cannot answer is who did it, which is the point.

Counting happens in memory and is flushed on a timer, so the hot path is a
dictionary increment and a slow disk never delays a response.
"""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DB_ENV_VAR = "HUB_USAGE_DB"
DEFAULT_DB = ".data/usage.db"

#: Seconds between flushes. Long enough that a busy minute is one write, short
#: enough that a restart loses little.
FLUSH_SECONDS = 30.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    hour     TEXT    NOT NULL,
    kind     TEXT    NOT NULL,
    object   TEXT    NOT NULL,
    selector TEXT    NOT NULL,
    client   TEXT    NOT NULL,
    status   INTEGER NOT NULL,
    count    INTEGER NOT NULL,
    PRIMARY KEY (hour, kind, object, selector, client, status)
) WITHOUT ROWID;
"""

#: One row per (hour, shape). `object` is a registry key or empty.
Key = tuple[str, str, str, str, str, int]

_COMMIT = re.compile(r"^[0-9a-f]{8}$")

#: The prefix of every path that says something about how the catalog is used.
#: Everything else, the health check included, is not counted at all rather
#: than counted and hidden.
_REFS = "/api/v1/refs/"

#: Segments that follow a reference and name an action rather than a commit.
_TAILS = {
    "pipeline.toml": "pull",
    "resolved": "resolve",
    "export": "resolve",
    "snippets": "resolve",
    "manifest": "fork",
}


def database_path() -> Path:
    return Path(os.getenv(DB_ENV_VAR) or DEFAULT_DB)


def client_of(user_agent: str) -> str:
    """Which family of caller this is, in one of three words.

    The raw string is never stored. A user agent is close enough to a
    fingerprint that keeping it would undo the point of counting rather than
    logging.
    """
    agent = user_agent.lower()
    if agent.startswith("piighost"):
        return "piighost"
    if "mozilla" in agent or "webkit" in agent:
        return "browser"
    return "other"


def selector_of(selector: str | None) -> str:
    """Whether the caller pinned, followed a tag, or took the head."""
    if selector is None or selector == "":
        return ""
    if selector == "latest":
        return "latest"
    return "commit" if _COMMIT.match(selector) else "tag"


def classify(path: str) -> tuple[str, str, str] | None:
    """The (kind, object, selector) a request counts as, or None to ignore it.

    A pull is the thing worth knowing: the library resolves a `catalog:`
    reference (`load_pipeline`, `catalogs = [...]`, `RegexDetector.from_catalog`,
    `piighost.catalog.pull`) by fetching the rendered pipeline, so
    `pipeline.toml` is counted apart from merely reading an object's metadata.
    """
    if path.startswith("/api/v1/search"):
        return ("search", "", "")
    if path.startswith("/api/v1/playground"):
        return ("playground", "", "")
    if path.startswith("/api/v1/submissions"):
        return ("submission", "", "")

    if not path.startswith(_REFS):
        return None
    parts = path[len(_REFS) :].split("/")
    if len(parts) < 2:
        return None
    key = f"{parts[0]}/{parts[1]}"
    rest = parts[2:]

    # `/refs/ns/name/manifest` names an action; `/refs/ns/name/prod` names a
    # commit. Both are one segment, so the literal wins and the rest is a
    # selector followed by an optional action.
    if len(rest) == 1 and rest[0] in _TAILS:
        return (_TAILS[rest[0]], key, "")
    if not rest:
        return ("browse", key, "")
    selector = selector_of(rest[0])
    if len(rest) == 1:
        return ("browse", key, selector)
    return (_TAILS.get(rest[1], "browse"), key, selector)


@dataclass(slots=True)
class Usage:
    """The in-memory tally and the file it drains into."""

    path: Path
    pending: Counter[Key]
    task: asyncio.Task[None] | None = None

    @classmethod
    def open(cls, path: Path) -> Usage:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            # WAL so a flush never blocks a read, and readers never block it.
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
        return cls(path=path, pending=Counter())

    def record(self, path: str, status: int, user_agent: str) -> None:
        """Count one request, in memory. Never raises, never blocks."""
        shape = classify(path)
        if shape is None:
            return
        kind, obj, selector = shape
        hour = datetime.now(UTC).strftime("%Y-%m-%dT%H")
        self.pending[(hour, kind, obj, selector, client_of(user_agent), status)] += 1

    async def flush(self) -> int:
        """Drain the tally into the file. Returns the number of rows written."""
        if not self.pending:
            return 0
        batch = self.pending
        self.pending = Counter()
        return await asyncio.to_thread(self._write, batch)

    def _write(self, batch: Counter[Key]) -> int:
        with sqlite3.connect(self.path, timeout=5.0) as db:
            db.executemany(
                "INSERT INTO usage (hour, kind, object, selector, client, status, count)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT DO UPDATE SET count = count + excluded.count",
                [(*key, count) for key, count in batch.items()],
            )
        return len(batch)

    async def run(self) -> None:
        """Flush on a timer until cancelled, then flush once more."""
        try:
            while True:
                await asyncio.sleep(FLUSH_SECONDS)
                await self.flush()
        except asyncio.CancelledError:
            await self.flush()
            raise


# ---------------------------------------------------------------- reading


@dataclass(slots=True)
class Row:
    key: str
    count: int


@dataclass(slots=True)
class Report:
    """What the stats page and `/api/v1/stats` show."""

    days: int
    since: str
    pulls: int
    browses: int
    searches: int
    per_day: list[Row]
    """Pulls per calendar day, oldest first, with the empty days kept."""
    top_objects: list[Row]
    selectors: list[Row]
    clients: list[Row]


def _since(days: int) -> str:
    """The first hour bucket inside the window, as a sortable prefix."""
    start = datetime.now(UTC).timestamp() - days * 86400
    return datetime.fromtimestamp(start, UTC).strftime("%Y-%m-%dT%H")


def report(path: Path, days: int = 30, top: int = 10) -> Report:
    """Aggregate the counters over a window.

    Read-only and synchronous: it runs against a file measured in kilobytes,
    and the alternative is a second connection pool for no gain.
    """
    since = _since(days)
    if not path.exists():
        return Report(days, since, 0, 0, 0, _series({}, days), [], [], [])

    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0) as db:

        def totals(kind: str) -> int:
            row = db.execute(
                "SELECT COALESCE(SUM(count), 0) FROM usage"
                " WHERE hour >= ? AND kind = ? AND status < 400",
                (since, kind),
            ).fetchone()
            return int(row[0])

        def grouped(column: str, where: str, limit: int) -> list[Row]:
            # `column` and `where` are literals written three lines below, never
            # anything a caller supplies; the window and the limit are bound.
            return [
                Row(key=str(key), count=int(count))
                for key, count in db.execute(
                    f"SELECT {column}, SUM(count) AS total FROM usage"
                    f" WHERE hour >= ? AND status < 400 AND {where}"
                    " GROUP BY 1 ORDER BY total DESC LIMIT ?",
                    (since, limit),
                )
            ]

        per_hour = {
            str(hour)[:10]: int(count)
            for hour, count in db.execute(
                "SELECT hour, SUM(count) FROM usage"
                " WHERE hour >= ? AND kind = 'pull' AND status < 400"
                " GROUP BY substr(hour, 1, 10)",
                (since,),
            )
        }
        return Report(
            days=days,
            since=since,
            pulls=totals("pull"),
            browses=totals("browse"),
            searches=totals("search"),
            per_day=_series(per_hour, days),
            top_objects=grouped("object", "kind = 'pull' AND object != ''", top),
            selectors=grouped("selector", "kind = 'pull' AND selector != ''", 8),
            clients=grouped("client", "kind = 'pull'", 8),
        )


def _series(per_day: dict[str, int], days: int) -> list[Row]:
    """One entry per day in the window, so a gap reads as a gap and not as absence."""
    today = datetime.now(UTC).timestamp()
    out = []
    for offset in range(days - 1, -1, -1):
        day = datetime.fromtimestamp(today - offset * 86400, UTC).strftime("%Y-%m-%d")
        out.append(Row(key=day, count=per_day.get(day, 0)))
    return out


def pulls_by_object(path: Path, days: int = 30) -> dict[str, int]:
    """How many times each object was pulled over a window.

    Read on the request rather than cached in the index: the table is measured
    in kilobytes and holds one row per (hour, shape), so the query is cheaper
    than the invalidation logic a cache would need.
    """
    if not path.exists():
        return {}
    since = _since(days)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0) as db:
        return {
            str(key): int(count)
            for key, count in db.execute(
                "SELECT object, SUM(count) FROM usage"
                " WHERE hour >= ? AND kind = 'pull' AND status < 400 AND object != ''"
                " GROUP BY object",
                (since,),
            )
        }
