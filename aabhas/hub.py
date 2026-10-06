"""Ties the cameras, the store and the operator together. The Flask app is a thin layer on top."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .camera import CLIP_FPS, CameraWorker
from .config import Settings
from .fall_machine import State
from .monitor import Event
from .pose import PoseEstimator
from .store import Store

URGENCY = {"ESCALATED": 0, "ALERT": 1, "DOWN": 2, "FALL": 2, "BEING_HELPED": 3, "RECOVERED": 4, "LOST": 4,
           "RESOLVED": 5, "UPRIGHT": 6, "LYING": 6}
OPEN_STATUS = ("open", "acknowledged", "dispatched")


@dataclass
class Active:
    """An alert that is still collecting skeleton frames and raw frames."""
    id: int
    camera: str
    track: int
    until: float                       # video time to stop recording at
    skeleton: list = field(default_factory=list)
    clip_n: int = 0
    last_clip_t: float = -1e9
    last_skel_t: float = -1e9


def _people(snap_people, subject: int) -> list[dict]:
    return [{"id": p.id, "subject": p.id == subject, "state": p.state.value, "box": p.box,
             "kpts": p.kpts, "scores": p.scores} for p in snap_people]


class Hub:
    def __init__(self, settings: Settings, pose: Optional[PoseEstimator] = None):
        self.s = settings
        self.store = Store(settings.data_dir)
        self.store.purge_old_clips(settings.clip_retention_hours)
        self.pose = pose or PoseEstimator(settings.pose_mode)
        self._pose_lock = threading.Lock()
        self._lock = threading.RLock()
        self.workers: dict[str, CameraWorker] = {}
        self.active: dict[int, Active] = {}
        self._purged = time.time()
        for c in settings.cameras:
            self.workers[c.id] = CameraWorker(c, self.pose, self._pose_lock, self._on_step,
                                              settings.process_fps, settings.replay_seconds)

    def start(self) -> None:
        for w in self.workers.values():
            w.start()

    def stop(self) -> None:
        for w in self.workers.values():
            w.stop()
        with self._lock:
            for aid in list(self.active):
                self._close(aid)

    # ---- worker callback -----------------------------------------------------------
    def _on_step(self, w: CameraWorker, events: list[Event]) -> None:
        with self._lock:
            for e in events:
                self._handle(w, e)
            for a in [a for a in self.active.values() if a.camera == w.cfg.id]:
                self._feed(w, a)
            if time.time() - self._purged > 600:
                self._purged = time.time()
                self.store.purge_old_clips(self.s.clip_retention_hours)

    def _open_alert(self, camera: str, track: int) -> Optional[dict]:
        for a in self.store.alerts(200):
            if a["camera"] == camera and a["track"] == track and a["status"] in OPEN_STATUS:
                return a
        return None

    def _handle(self, w: CameraWorker, e: Event) -> None:
        eid = self.store.add_event(e.camera, e.track, e.t, e.type, e.reason, e.info)
        if e.type == "ALERT":
            self._open(w, e)
            return
        alert = self._open_alert(e.camera, e.track)
        if alert is None:
            if e.type in ("BEING_HELPED", "RECOVERED"):
                snap = w.monitor.skeleton_replay(e.track, since=e.t - 10.0)
                d = self.store.root / "events"
                d.mkdir(exist_ok=True)
                (d / f"{eid}.json").write_text(json.dumps({**snap, "size": list(w.size)}, separators=(",", ":")))
            return
        if e.type in ("ESCALATED", "BEING_HELPED", "DOWN"):
            self.store.update_alert(alert["id"], state=e.type)
        elif e.type in ("RECOVERED", "LOST"):
            self.store.update_alert(alert["id"], state=e.type, status="closed", end_t=e.t)
            self._close(alert["id"])

    def _open(self, w: CameraWorker, e: Event) -> None:
        fall_t = float(e.info.get("fall_t", e.t))
        aid = self.store.add_alert(e.camera, w.cfg.location, e.track, fall_t, e.t, "ALERT")
        act = Active(aid, e.camera, e.track, until=e.t + self.s.clip_after_alert_s)
        act.skeleton = w.monitor.skeleton_replay(e.track, since=fall_t - 6.0)["frames"]
        act.last_skel_t = e.t
        clip_dir = self.store.clip_dir(aid)
        for t, jpg in list(w.raw):
            if t >= fall_t - 6.0:
                (clip_dir / f"{act.clip_n:05d}.jpg").write_bytes(jpg)
                act.clip_n += 1
                act.last_clip_t = t
        self.active[aid] = act
        self.store.update_alert(aid, clip_frames=act.clip_n, clip_fps=CLIP_FPS)
        self._save_skeleton(w, act)

    def _feed(self, w: CameraWorker, a: Active) -> None:
        t = w.t
        snap = w.monitor.replay[-1] if w.monitor.replay else None
        if snap is not None and t - a.last_skel_t >= 0.2 and t <= a.until:
            a.last_skel_t = t
            a.skeleton.append({"t": round(snap.t, 2), "people": _people(snap.people, a.track)})
        if t <= a.until and w.raw and w.raw[-1][0] > a.last_clip_t:
            tt, jpg = w.raw[-1]
            (self.store.clip_dir(a.id) / f"{a.clip_n:05d}.jpg").write_bytes(jpg)
            a.clip_n += 1
            a.last_clip_t = tt
        if t > a.until:
            self._close(a.id)

    def _save_skeleton(self, w: CameraWorker, a: Active) -> None:
        self.store.write_skeleton(a.id, {"subject": a.track, "size": list(w.size), "frames": a.skeleton})

    def _close(self, alert_id: int) -> None:
        a = self.active.pop(alert_id, None)
        if a is None:
            return
        self._save_skeleton(self.workers[a.camera], a)
        row = self.store.alert(alert_id)
        if row and row["status"] != "false_alarm":
            self.store.update_alert(alert_id, clip_frames=a.clip_n)

    # ---- operator -----------------------------------------------------------------
    def operator(self, alert_id: int, action: str) -> dict:
        with self._lock:
            row = self.store.alert(alert_id)
            if row is None:
                raise KeyError(alert_id)
            w = self.workers[row["camera"]]
            if action == "acknowledge":
                w.monitor.acknowledge(row["track"])
                self.store.update_alert(alert_id, status="acknowledged")
            elif action == "dispatch":
                w.monitor.dispatch(row["track"])
                self.store.update_alert(alert_id, status="dispatched")
            elif action == "false_alarm":
                for e in w.monitor.false_alarm(row["track"]):
                    self.store.add_event(e.camera, e.track, e.t, e.type, e.reason, {})
                self.store.update_alert(alert_id, status="false_alarm", state="RESOLVED", end_t=w.t)
                self._close(alert_id)
                self.store.delete_clip(alert_id)
            else:
                raise ValueError(action)
            self.store.add_event(row["camera"], row["track"], w.t, "OPERATOR", f"{action} alert {alert_id}", {})
            return self.store.alert(alert_id)

    def log_raw_access(self, alert_id: int) -> None:
        row = self.store.alert(alert_id)
        if row:
            self.store.add_event(row["camera"], row["track"], self.workers[row["camera"]].t, "OPERATOR",
                                 f"opened raw clip of alert {alert_id}", {})

    # ---- read side ----------------------------------------------------------------
    def skeleton(self, alert_id: int) -> Optional[dict]:
        with self._lock:
            a = self.active.get(alert_id)
            if a is not None:
                return {"subject": a.track, "size": list(self.workers[a.camera].size), "frames": list(a.skeleton)}
        return self.store.read_skeleton(alert_id)

    def snapshot(self) -> dict:
        cams, watching = [], []
        for w in self.workers.values():
            with w.lock:
                t, size = w.t, w.size
            people = list(w.monitor.people)
            worst = "UPRIGHT" if not people else min((p.state.value for p in people), key=lambda s: URGENCY.get(s, 9))
            for p in people:
                if p.state in (State.FALL, State.DOWN):
                    watching.append({"camera": w.cfg.id, "name": w.cfg.name, "location": w.cfg.location,
                                     "track": p.id, "state": p.state.value, "countdown": p.countdown,
                                     "down_for": p.down_for})
            cams.append({"id": w.cfg.id, "name": w.cfg.name, "location": w.cfg.location, "status": w.status,
                         "fps": round(w.fps, 1), "t": round(t, 1), "people": len(people), "size": list(size),
                         "state": worst})
        alerts = []
        for a in self.store.alerts(50):
            w = self.workers.get(a["camera"])
            live = a["status"] in OPEN_STATUS
            end = a["end_t"] if a["end_t"] is not None else a["alert_t"]
            now_t = w.t if (w and live) else end
            urgency = URGENCY.get(a["state"], 2) + (0.5 if a["status"] in ("acknowledged", "dispatched") else 0)
            alerts.append({**a, "since_fall": round(now_t - a["fall_t"], 1), "live": live, "urgency": urgency})
        alerts.sort(key=lambda a: (not a["live"], a["urgency"], -a["id"]))
        return {"cameras": cams, "alerts": alerts, "watching": watching, "events": self.store.events(60),
                "server_time": time.time()}
