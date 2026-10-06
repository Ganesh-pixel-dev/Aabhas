"""SQLite store for events and alerts. Skeleton JSON and raw clips live next to it on disk.

What is kept, and for how long:
  events    every state change (text and bounding box only). Kept until you delete the file.
  skeleton  pose lines for an alert or a recovery, no pixels from the camera. Kept with the event.
  raw clip  JPEG frames, written only for alerted events, deleted after clip_retention_hours
            or at once if the operator marks the alert a false alarm.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, wall REAL, video_t REAL, camera TEXT, track INTEGER,
  type TEXT, reason TEXT, info TEXT);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, camera TEXT, location TEXT, track INTEGER,
  wall REAL, fall_t REAL, alert_t REAL, end_t REAL, state TEXT, status TEXT,
  clip_frames INTEGER DEFAULT 0, clip_fps REAL DEFAULT 5, note TEXT);
"""


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.root / "aabhas.sqlite", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    # ---- events -------------------------------------------------------------
    def add_event(self, camera: str, track: int, video_t: float, type_: str, reason: str, info: dict) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO events(wall, video_t, camera, track, type, reason, info) VALUES (?,?,?,?,?,?,?)",
                (time.time(), video_t, camera, track, type_, reason, json.dumps(info)))
            self._db.commit()
            return int(cur.lastrowid)

    def events(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---- alerts -------------------------------------------------------------
    def add_alert(self, camera: str, location: str, track: int, fall_t: float, alert_t: float, state: str) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO alerts(camera, location, track, wall, fall_t, alert_t, state, status) VALUES (?,?,?,?,?,?,?,'open')",
                (camera, location, track, time.time(), fall_t, alert_t, state))
            self._db.commit()
            return int(cur.lastrowid)

    def update_alert(self, alert_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self._db.execute(f"UPDATE alerts SET {cols} WHERE id=?", (*fields.values(), alert_id))
            self._db.commit()

    def alert(self, alert_id: int) -> Optional[dict]:
        with self._lock:
            r = self._db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        return dict(r) if r else None

    def alerts(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---- files --------------------------------------------------------------
    def alert_dir(self, alert_id: int) -> Path:
        d = self.root / "alerts" / str(alert_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_skeleton(self, alert_id: int, data: dict) -> None:
        (self.alert_dir(alert_id) / "skeleton.json").write_text(json.dumps(data, separators=(",", ":")))

    def read_skeleton(self, alert_id: int) -> Optional[dict]:
        p = self.root / "alerts" / str(alert_id) / "skeleton.json"
        return json.loads(p.read_text()) if p.exists() else None

    def clip_dir(self, alert_id: int) -> Path:
        d = self.alert_dir(alert_id) / "clip"
        d.mkdir(exist_ok=True)
        return d

    def delete_clip(self, alert_id: int) -> None:
        shutil.rmtree(self.root / "alerts" / str(alert_id) / "clip", ignore_errors=True)
        self.update_alert(alert_id, clip_frames=0)

    def purge_old_clips(self, retention_hours: float) -> int:
        cutoff = time.time() - retention_hours * 3600
        n = 0
        for a in self.alerts(limit=10_000):
            if a["clip_frames"] and a["wall"] < cutoff:
                self.delete_clip(a["id"])
                n += 1
        return n
