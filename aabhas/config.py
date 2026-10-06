"""Every threshold lives here. One `Thresholds` per camera, overridable from YAML.

Distances are in body heights (the person's own standing height in pixels), so the
same numbers work for a person near the camera and a person far from it. Times are
in seconds of video time.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Thresholds:
    # Posture. Torso angle is measured from vertical: 0 is standing, 90 is flat.
    upright_angle_deg: float = 35.0
    horizontal_angle_deg: float = 55.0
    upright_height_ratio: float = 0.75   # box height / standing height counts as upright above this
    low_height_ratio: float = 0.65       # a wide box lower than this counts as lying

    # FALL trigger: fast drop of the body centre while the torso goes flat.
    fall_window_s: float = 1.5
    drop_frac: float = 0.30              # centre drop, in body heights, within fall_window_s
    min_peak_speed: float = 0.5          # body heights per second, fastest 0.3 s inside the window
    min_track_age_s: float = 1.0         # ignore tracks younger than this

    # FALL -> DOWN -> RECOVERED
    settle_s: float = 2.0                # still not upright this long after the drop: DOWN
    getup_s: float = 1.5                 # upright this long: RECOVERED
    recovered_hold_s: float = 3.0        # RECOVERED shows this long, then plain UPRIGHT
    lying_s: float = 3.0                 # low for this long with no fall: LYING (never alerts)

    # DOWN -> ALERT
    down_seconds: float = 30.0           # time on the ground, counted from the start of the fall

    # Help: someone else stops near the fallen person.
    help_radius: float = 1.5             # body heights from the fallen person's centre
    help_dwell_s: float = 3.0            # they must stay (and stay still) this long
    help_still_speed: float = 0.4        # body heights per second, below this is "stopped"
    help_leave_s: float = 5.0            # helper gone this long: back to DOWN

    # ALERT -> ESCALATED
    escalate_after_s: float = 180.0      # unacknowledged for this long

    # Tracking
    track_lost_s: float = 1.5            # drop an ordinary track after this long unseen
    track_sticky_s: float = 90.0         # keep a fallen person's track this long unseen
    track_min_hits: int = 3
    track_iou: float = 0.2
    track_max_dist: float = 1.0          # centroid gate, in box diagonals

    def with_overrides(self, overrides: dict[str, Any] | None) -> "Thresholds":
        if not overrides:
            return self
        known = {f.name for f in fields(self)}
        bad = set(overrides) - known
        if bad:
            raise ValueError(f"unknown threshold(s): {sorted(bad)}")
        return replace(self, **overrides)


@dataclass
class CameraConfig:
    id: str
    name: str
    location: str
    source: str | int
    crop: tuple[int, int, int, int] | None = None   # x, y, w, h in source pixels
    loop: bool = False
    speed: float = 1.0                  # playback speed for video files
    thresholds: Thresholds = field(default_factory=Thresholds)


@dataclass
class Settings:
    cameras: list[CameraConfig]
    data_dir: Path
    pose_mode: str = "balanced"          # rtmlib: lightweight | balanced | performance
    process_fps: float = 10.0            # upper bound per camera
    replay_seconds: float = 25.0         # skeleton replay kept before an alert
    clip_retention_hours: float = 72.0   # raw clips of alerted events only
    clip_after_alert_s: float = 60.0
    host: str = "127.0.0.1"
    port: int = 5000


def load_settings(path: str | Path) -> Settings:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = Thresholds().with_overrides(raw.get("thresholds"))
    cams = []
    for c in raw["cameras"]:
        src = c["source"]
        if isinstance(src, str) and not src.startswith(("rtsp://", "http://", "https://")):
            p = Path(src)
            src = str(p if p.is_absolute() else ROOT / p)
        crop = tuple(c["crop"]) if c.get("crop") else None
        cams.append(CameraConfig(
            id=c["id"], name=c["name"], location=c["location"], source=src, crop=crop,
            loop=bool(c.get("loop", False)), speed=float(c.get("speed", 1.0)),
            thresholds=defaults.with_overrides(c.get("thresholds")),
        ))
    s = raw.get("settings", {})
    data_dir = Path(s.pop("data_dir", "runtime"))
    return Settings(cameras=cams, data_dir=data_dir if data_dir.is_absolute() else ROOT / data_dir, **s)
