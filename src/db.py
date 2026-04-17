"""
SQLite storage for pipeline run history.
Stores every run and classification so you can query, compare, and analyze across time.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "pipeline_history.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    path = db_path or DEFAULT_DB_PATH
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            model           TEXT    NOT NULL,
            prompt_version  TEXT    NOT NULL,
            mode            TEXT    NOT NULL DEFAULT 'dummy',
            dataset_size    INTEGER NOT NULL DEFAULT 0,
            pass_count      INTEGER NOT NULL DEFAULT 0,
            pass_rate       REAL    NOT NULL DEFAULT 0.0,
            flag            TEXT    NOT NULL DEFAULT 'OK',
            delta           REAL    NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS classifications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            case_id         TEXT    NOT NULL,
            input_text      TEXT,
            expected_cat    TEXT,
            predicted_cat   TEXT,
            expected_summary TEXT,
            predicted_summary TEXT,
            correct         INTEGER NOT NULL DEFAULT 0,
            latency         REAL    NOT NULL DEFAULT 0.0
        );

        CREATE INDEX IF NOT EXISTS idx_classifications_run_id ON classifications(run_id);
        CREATE INDEX IF NOT EXISTS idx_classifications_case_id ON classifications(case_id);

        CREATE TABLE IF NOT EXISTS diffs (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id                INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            prev_run_id           INTEGER REFERENCES runs(id) ON DELETE SET NULL,
            global_pass_rate_prev REAL    NOT NULL DEFAULT 0.0,
            global_pass_rate_curr REAL    NOT NULL DEFAULT 0.0,
            delta                 REAL    NOT NULL DEFAULT 0.0,
            flag                  TEXT    NOT NULL DEFAULT 'OK',
            per_category_prev     TEXT    NOT NULL DEFAULT '{}',
            per_category_curr     TEXT    NOT NULL DEFAULT '{}',
            regressions           TEXT    NOT NULL DEFAULT '[]',
            improvements          TEXT    NOT NULL DEFAULT '[]'
        );

        CREATE INDEX IF NOT EXISTS idx_diffs_run_id ON diffs(run_id);
    """)
    conn.commit()


def save_run(
    conn: sqlite3.Connection,
    diff_data: dict[str, Any],
    raw_outputs: list[dict[str, Any]],
    model: str,
    prompt_version: str,
    mode: str = "dummy",
) -> int:
    """Insert a pipeline run and all its classifications. Returns the run ID."""
    now = datetime.now().isoformat(timespec="seconds")
    pass_count = sum(1 for r in raw_outputs if r.get("category_match"))
    dataset_size = len(raw_outputs)
    pass_rate = pass_count / dataset_size if dataset_size else 0.0

    cursor = conn.execute(
        """
        INSERT INTO runs (timestamp, model, prompt_version, mode, dataset_size, pass_count, pass_rate, flag, delta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            model,
            prompt_version,
            mode,
            dataset_size,
            pass_count,
            round(pass_rate, 4),
            diff_data.get("flag", "OK"),
            round(diff_data.get("delta", 0.0), 4),
        ),
    )
    run_id = cursor.lastrowid

    classifications = []
    for r in raw_outputs:
        expected = r.get("expected_output", {})
        classifications.append(
            (
                run_id,
                str(r.get("id", "")),
                r.get("input", ""),
                expected.get("category", ""),
                r.get("category", ""),
                expected.get("summary", ""),
                r.get("summary", ""),
                1 if r.get("category_match") else 0,
                r.get("latency", 0.0),
            )
        )

    conn.executemany(
        """
        INSERT INTO classifications
            (run_id, case_id, input_text, expected_cat, predicted_cat,
             expected_summary, predicted_summary, correct, latency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        classifications,
    )
    conn.commit()
    return run_id


def get_run(conn: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    """Get a single run by ID."""
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def get_latest_runs(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    """Get the N most recent runs, newest first."""
    rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_classifications(conn: sqlite3.Connection, run_id: int) -> list[dict[str, Any]]:
    """Get all classifications for a given run."""
    rows = conn.execute(
        "SELECT * FROM classifications WHERE run_id = ? ORDER BY case_id",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_case_history(conn: sqlite3.Connection, case_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Track a specific test case across runs."""
    rows = conn.execute(
        """
        SELECT c.*, r.timestamp, r.model, r.prompt_version
        FROM classifications c
        JOIN runs r ON c.run_id = r.id
        WHERE c.case_id = ?
        ORDER BY r.id DESC
        LIMIT ?
        """,
        (case_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_category_history(conn: sqlite3.Connection, category: str, limit: int = 20) -> list[dict[str, Any]]:
    """Get accuracy trend for a specific category across runs."""
    rows = conn.execute(
        """
        SELECT r.id AS run_id, r.timestamp, r.model, r.prompt_version,
               COUNT(*) AS total,
               SUM(c.correct) AS correct,
               ROUND(CAST(SUM(c.correct) AS REAL) / COUNT(*), 4) AS accuracy
        FROM classifications c
        JOIN runs r ON c.run_id = r.id
        WHERE c.expected_cat = ?
        GROUP BY r.id
        ORDER BY r.id DESC
        LIMIT ?
        """,
        (category, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def compare_runs(conn: sqlite3.Connection, run_id_a: int, run_id_b: int) -> list[dict[str, Any]]:
    """Compare classifications between two runs. Returns cases that differ."""
    rows = conn.execute(
        """
        SELECT
            a.case_id,
            a.expected_cat,
            a.predicted_cat  AS predicted_a,
            b.predicted_cat  AS predicted_b,
            a.correct        AS correct_a,
            b.correct        AS correct_b
        FROM classifications a
        JOIN classifications b ON a.case_id = b.case_id
        WHERE a.run_id = ? AND b.run_id = ?
          AND a.correct != b.correct
        ORDER BY a.case_id
        """,
        (run_id_a, run_id_b),
    ).fetchall()
    return [dict(r) for r in rows]


def get_summary_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Get high-level stats across all runs."""
    run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    if run_count == 0:
        return {"total_runs": 0, "total_classifications": 0}

    stats = conn.execute("""
        SELECT
            COUNT(*)                    AS total_runs,
            AVG(pass_rate)              AS avg_pass_rate,
            MIN(pass_rate)              AS min_pass_rate,
            MAX(pass_rate)              AS max_pass_rate,
            MIN(timestamp)              AS first_run,
            MAX(timestamp)              AS last_run
        FROM runs
    """).fetchone()

    total_classifications = conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]

    return {
        **dict(stats),
        "total_classifications": total_classifications,
    }


def get_latest_run_id(conn: sqlite3.Connection) -> int | None:
    """Return the ID of the most recent run, or None if no runs exist."""
    row = conn.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def get_run_results_as_dict(conn: sqlite3.Connection, run_id: int) -> dict[str, dict[str, Any]]:
    """Load classifications for a run in the same format as diff_eval.load_results().

    Returns a dict keyed by case_id with fields compatible with diff_eval's logic.
    """
    rows = get_classifications(conn, run_id)
    return {
        r["case_id"]: {
            "id": r["case_id"],
            "category_match": bool(r["correct"]),
            "category": r["predicted_cat"],
            "expected_output": {"category": r["expected_cat"], "summary": r.get("expected_summary", "")},
            "summary": r.get("predicted_summary", ""),
            "input": r.get("input_text", ""),
            "latency": r.get("latency", 0.0),
        }
        for r in rows
    }


def save_diff(
    conn: sqlite3.Connection,
    run_id: int,
    prev_run_id: int | None,
    diff_data: dict[str, Any],
) -> int:
    """Save comparison/diff results to the diffs table. Returns the diff ID."""
    cursor = conn.execute(
        """
        INSERT INTO diffs
            (run_id, prev_run_id, global_pass_rate_prev, global_pass_rate_curr,
             delta, flag, per_category_prev, per_category_curr, regressions, improvements)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            prev_run_id,
            diff_data.get("global_pass_rate_prev", 0.0),
            diff_data.get("global_pass_rate_curr", 0.0),
            diff_data.get("delta", 0.0),
            diff_data.get("flag", "OK"),
            json.dumps(diff_data.get("per_category_prev", {})),
            json.dumps(diff_data.get("per_category_curr", {})),
            json.dumps(diff_data.get("regressions", [])),
            json.dumps(diff_data.get("improvements", [])),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_diff(conn: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    """Get the diff record for a given run."""
    row = conn.execute("SELECT * FROM diffs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["per_category_prev"] = json.loads(d["per_category_prev"])
    d["per_category_curr"] = json.loads(d["per_category_curr"])
    d["regressions"] = json.loads(d["regressions"])
    d["improvements"] = json.loads(d["improvements"])
    return d


def get_latest_diffs(conn: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    """Get the N most recent diffs, newest first."""
    rows = conn.execute("SELECT * FROM diffs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["per_category_prev"] = json.loads(d["per_category_prev"])
        d["per_category_curr"] = json.loads(d["per_category_curr"])
        d["regressions"] = json.loads(d["regressions"])
        d["improvements"] = json.loads(d["improvements"])
        result.append(d)
    return result
