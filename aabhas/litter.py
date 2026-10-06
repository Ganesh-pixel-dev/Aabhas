"""EXPERIMENTAL. Littering hotspots: a new object appears on the ground, stays, and a person was
standing right there when it appeared.

Two background models run at different speeds. A thing that was not in the slow background
but is already absorbed by the fast one has arrived and stopped moving. It becomes an event only
if a person's box was next to that spot in the seconds before. It does not say what the object is.
A bag set down on purpose looks the same as a dropped wrapper, so counts are hotspots, not verdicts.
"""
from __future__ import annotations

import csv
import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class LitterParams:
    width: int = 320                 # frames are scaled to this width
    tau_fast_s: float = 6.0
    tau_slow_s: float = 240.0
    diff: int = 28
    min_area_frac: float = 0.0006
    max_area_frac: float = 0.03
    static_s: float = 20.0           # must stay this long before it counts
    assoc_s: float = 8.0             # a person must have been this close within this long before it showed up
    assoc_margin: float = 0.4        # person box grown by this fraction of its height
    match_px: float = 14.0
    warmup_s: float = 15.0


@dataclass
class LitterEvent:
    t: float
    x: float          # 0..1 across the frame
    y: float
    area_frac: float


@dataclass
class _Cand:
    first_t: float
    last_t: float
    cx: float
    cy: float
    area: float
    near_person: bool
    fired: bool = False


class LitterDetector:
    def __init__(self, p: LitterParams | None = None):
        self.p = p or LitterParams()
        self.fast = self.slow = None
        self.t0 = None
        self.last_t = None
        self.people: deque = deque()     # (t, boxes scaled)
        self.cands: list[_Cand] = []

    def update(self, t: float, frame_bgr: np.ndarray, person_boxes: list) -> list[LitterEvent]:
        p = self.p
        h0, w0 = frame_bgr.shape[:2]
        k = p.width / w0
        small = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(frame_bgr, (p.width, int(h0 * k))), cv2.COLOR_BGR2GRAY), (5, 5), 0).astype(np.float32)
        boxes = [tuple(float(v) * k for v in b) for b in person_boxes]
        self.people.append((t, boxes))
        while self.people and t - self.people[0][0] > p.assoc_s + 2:
            self.people.popleft()
        if self.fast is None:
            self.fast, self.slow, self.t0, self.last_t = small.copy(), small.copy(), t, t
            return []
        dt = max(t - self.last_t, 1e-3)
        self.last_t = t
        fg_slow = np.abs(small - self.slow) > p.diff
        fg_fast = np.abs(small - self.fast) > p.diff
        self.fast += (1 - math.exp(-dt / p.tau_fast_s)) * (small - self.fast)
        self.slow += (1 - math.exp(-dt / p.tau_slow_s)) * (small - self.slow)
        if t - self.t0 < p.warmup_s:
            return []
        static = (fg_slow & ~fg_fast).astype(np.uint8) * 255
        for b in boxes:                                  # moving people are not litter
            x1, y1, x2, y2 = (int(v) for v in b)
            static[max(0, y1):max(0, y2), max(0, x1):max(0, x2)] = 0
        static = cv2.morphologyEx(static, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        static = cv2.morphologyEx(static, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        n, _, stats, cents = cv2.connectedComponentsWithStats(static)
        area_all = static.shape[0] * static.shape[1]
        seen = []
        for i in range(1, n):
            a = stats[i, cv2.CC_STAT_AREA] / area_all
            if p.min_area_frac <= a <= p.max_area_frac:
                seen.append((float(cents[i][0]), float(cents[i][1]), a))
        events = []
        for cx, cy, a in seen:
            c = next((c for c in self.cands if math.hypot(c.cx - cx, c.cy - cy) <= p.match_px), None)
            if c is None:
                self.cands.append(_Cand(t, t, cx, cy, a, self._person_near(t, cx, cy)))
                continue
            c.last_t, c.cx, c.cy, c.area = t, cx, cy, a
            if not c.fired and c.near_person and t - c.first_t >= p.static_s:
                c.fired = True
                events.append(LitterEvent(t, cx / static.shape[1], cy / static.shape[0], a))
        self.cands = [c for c in self.cands if t - c.last_t <= 3.0]
        return events

    def _person_near(self, t: float, cx: float, cy: float) -> bool:
        m = self.p.assoc_margin
        for pt, boxes in self.people:
            if t - pt > self.p.assoc_s:
                continue
            for x1, y1, x2, y2 in boxes:
                g = (y2 - y1) * m
                if x1 - g <= cx <= x2 + g and y1 - g <= cy <= y2 + g:
                    return True
        return False


def hotspot_rows(events: list[dict]) -> list[dict]:
    """events: dicts with camera, place, hour. Returns counts per camera, place and hour of day."""
    counts: dict[tuple, int] = {}
    for e in events:
        key = (e["camera"], e["place"], int(e["hour"]))
        counts[key] = counts.get(key, 0) + 1
    return [{"camera": c, "place": p, "hour": h, "count": n} for (c, p, h), n in sorted(counts.items())]


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["camera", "place", "hour", "count"])
        w.writeheader()
        w.writerows(rows)
