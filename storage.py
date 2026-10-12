"""Transactional SQLite state, completed batches, incidents and collection lease."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import time
import uuid

import pandas as pd

from collector import utc_now
from diagnosis import diagnose_live
from settings import Settings
from state import EndpointState, transition


class Store:
    def __init__(self, path: str | Path = "data/pingshield.sqlite"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("Database schema is newer than this application")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, network TEXT NOT NULL, diagnosis TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS measurements(batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                    endpoint TEXT NOT NULL, timestamp TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(batch_id, endpoint));
                CREATE INDEX IF NOT EXISTS measurement_time ON measurements(timestamp);
                CREATE INDEX IF NOT EXISTS endpoint_history ON measurements(endpoint, timestamp);
                CREATE TABLE IF NOT EXISTS states(endpoint TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, endpoint TEXT NOT NULL, started TEXT NOT NULL,
                    ended TEXT, severity TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
                    evidence TEXT NOT NULL, actions TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '');
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_incident ON incidents(endpoint) WHERE ended IS NULL;
                CREATE TABLE IF NOT EXISTS lease(id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, expires REAL NOT NULL);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            with conn:
                yield conn
        finally:
            conn.close()

    def acquire(self, owner: str, ttl: float = 120) -> bool:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT owner,expires FROM lease WHERE id=1").fetchone()
            if old and old["expires"] > time.time() and old["owner"] != owner:
                return False
            conn.execute("INSERT OR REPLACE INTO lease VALUES(1,?,?)", (owner, time.time() + ttl))
            return True

    def release(self, owner: str) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM lease WHERE id=1 AND owner=?", (owner,))

    def save_batch(
        self, df: pd.DataFrame, settings: Settings, network: dict, batch_id: str | None = None
    ) -> pd.DataFrame:
        if not df.empty and (df["mode"] != "live").any():
            raise ValueError("Simulation must never enter the live store")
        # Pandas serializes numpy scalars/NaN into ordinary JSON numbers/null.
        records = json.loads(df.to_json(orient="records"))
        batch_id = batch_id or str(uuid.uuid4())
        timestamp = max((r["timestamp"] for r in records), default=utc_now())
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM batches WHERE id=?", (batch_id,)).fetchone():
                return self._batch(conn, batch_id)
            latest = conn.execute("SELECT timestamp FROM batches ORDER BY timestamp DESC LIMIT 1").fetchone()
            if latest and timestamp <= latest["timestamp"]:
                raise ValueError("Out-of-order measurement batch rejected")
            active_ids = {r["id"] for r in records}
            # Removed targets are closed as configuration changes, never marked recovered.
            for incident in conn.execute("SELECT id,endpoint FROM incidents WHERE ended IS NULL").fetchall():
                if incident["endpoint"] not in active_ids:
                    conn.execute(
                        "UPDATE incidents SET ended=?,status='RESOLVED',notes='Target removed from active configuration; recovery not verified' WHERE id=?",
                        (timestamp, incident["id"]),
                    )
            for row in records:
                stored = conn.execute("SELECT data FROM states WHERE endpoint=?", (row["id"],)).fetchone()
                previous = EndpointState(**json.loads(stored["data"])) if stored else EndpointState()
                state = transition(previous, row, settings)
                row["previous_status"] = previous.status
                row["status"] = state.status
                conn.execute(
                    "INSERT OR REPLACE INTO states VALUES(?,?)", (row["id"], json.dumps(state.as_dict()))
                )
                incident = conn.execute(
                    "SELECT * FROM incidents WHERE endpoint=? AND ended IS NULL", (row["id"],)
                ).fetchone()
                detail = json.dumps({"batch_id": batch_id, "measurement": row})
                if state.status in {"CRITICAL", "UNREACHABLE"}:
                    if not incident:
                        conn.execute(
                            "INSERT INTO incidents(id,endpoint,started,severity,status,reason,evidence,actions) VALUES(?,?,?,?,?,?,?,?)",
                            (
                                str(uuid.uuid4()),
                                row["id"],
                                timestamp,
                                state.status,
                                "OPEN",
                                f"Confirmed {row['raw_status']} after {state.failures} windows",
                                detail,
                                "[]",
                            ),
                        )
                    else:
                        conn.execute(
                            "UPDATE incidents SET status='OPEN',severity=?,evidence=? WHERE id=?",
                            (state.status, detail, incident["id"]),
                        )
                elif incident and state.status == "HEALTHY":
                    conn.execute(
                        "UPDATE incidents SET ended=?,status='RESOLVED',evidence=? WHERE id=?",
                        (timestamp, detail, incident["id"]),
                    )
                elif incident:
                    conn.execute(
                        "UPDATE incidents SET status=?,evidence=? WHERE id=?",
                        (
                            "RECOVERING" if state.status == "RECOVERING" else incident["status"],
                            detail,
                            incident["id"],
                        ),
                    )
                active = conn.execute(
                    "SELECT id FROM incidents WHERE endpoint=? AND ended IS NULL", (row["id"],)
                ).fetchone()
                row["incident_id"] = active["id"] if active else (incident["id"] if incident else None)
            normalized = pd.DataFrame(records) if records else df.copy()
            diagnosis = diagnose_live(normalized, network)
            conn.execute(
                "INSERT INTO batches VALUES(?,?,?,?)",
                (batch_id, timestamp, json.dumps(network), json.dumps(diagnosis.__dict__)),
            )
            for row in records:
                conn.execute(
                    "INSERT INTO measurements VALUES(?,?,?,?)",
                    (batch_id, row["id"], row["timestamp"], json.dumps(row)),
                )
            conn.execute(
                "UPDATE incidents SET actions=? WHERE ended IS NULL", (json.dumps(diagnosis.actions),)
            )
            cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.retention_days)).isoformat()
            conn.execute("DELETE FROM batches WHERE timestamp<?", (cutoff,))
            conn.execute(
                "DELETE FROM batches WHERE id NOT IN (SELECT id FROM batches ORDER BY timestamp DESC LIMIT ?)",
                (settings.max_batches,),
            )
            conn.execute("DELETE FROM incidents WHERE ended IS NOT NULL AND ended<?", (cutoff,))
            # Also bound resolved incidents by count; active incidents are at most one per endpoint.
            conn.execute(
                "DELETE FROM incidents WHERE ended IS NOT NULL AND id NOT IN (SELECT id FROM incidents WHERE ended IS NOT NULL ORDER BY ended DESC LIMIT ?)",
                (settings.max_batches,),
            )
            conn.execute(
                "DELETE FROM states WHERE endpoint NOT IN (SELECT DISTINCT endpoint FROM measurements) AND endpoint NOT IN (SELECT endpoint FROM incidents WHERE ended IS NULL)"
            )
        return normalized

    @staticmethod
    def _batch(conn, batch_id: str) -> pd.DataFrame:
        rows = conn.execute(
            "SELECT data FROM measurements WHERE batch_id=? ORDER BY endpoint", (batch_id,)
        ).fetchall()
        return pd.DataFrame([json.loads(r["data"]) for r in rows])

    def latest(self) -> tuple[pd.DataFrame, dict]:
        with self.connection() as conn:
            batch = conn.execute("SELECT * FROM batches ORDER BY timestamp DESC LIMIT 1").fetchone()
            return (
                (self._batch(conn, batch["id"]), json.loads(batch["network"]))
                if batch
                else (pd.DataFrame(), {})
            )

    def last_success_time(self) -> str | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT max(timestamp) AS latest FROM measurements WHERE json_extract(data, '$.success_count') > 0"
            ).fetchone()
            return row["latest"] if row else None

    def history(self, limit: int = 2000) -> pd.DataFrame:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT data FROM measurements ORDER BY timestamp DESC LIMIT ?", (min(max(limit, 1), 20000),)
            ).fetchall()
            return pd.DataFrame([json.loads(r["data"]) for r in rows])

    def incidents(self) -> pd.DataFrame:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM incidents ORDER BY started DESC LIMIT 10000").fetchall()
        data = [dict(r) for r in rows]
        now = datetime.now(timezone.utc)
        for row in data:
            end = datetime.fromisoformat(row["ended"]) if row["ended"] else now
            row["duration_seconds"] = round((end - datetime.fromisoformat(row["started"])).total_seconds(), 1)
        return pd.DataFrame(data)

    def annotate(self, incident_id: str, notes: str, acknowledge: bool = False) -> None:
        if len(notes) > 2000:
            raise ValueError("Notes exceed 2000 characters")
        with self.connection() as conn:
            conn.execute("UPDATE incidents SET notes=? WHERE id=?", (notes, incident_id))
            if acknowledge:
                conn.execute(
                    "UPDATE incidents SET status='ACKNOWLEDGED' WHERE id=? AND status='OPEN'", (incident_id,)
                )
