"""A small IoU + centroid tracker. Greedy-free: Hungarian assignment on a combined cost.

A person who has fallen changes shape a lot (tall box to wide box), so IoU alone loses them.
Pairs with little overlap can still match if their centres are close, measured in box diagonals.
Tracks of people on the ground are kept for much longer than ordinary ones, because a person
lying down is exactly the one the detector misses and finds again.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from .config import Thresholds
from .fall_machine import FallMachine
from .pose import Detection


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def centre(b: np.ndarray) -> np.ndarray:
    return np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2])


@dataclass
class Track:
    id: int
    box: np.ndarray
    kpts: np.ndarray
    scores: np.ndarray
    born_t: float
    last_t: float
    hits: int = 1
    matched_now: bool = True
    machine: Optional[FallMachine] = None
    trail: deque = field(default_factory=lambda: deque(maxlen=64))   # (t, cx, cy)

    def speed(self, body_px: float, window: float = 1.0) -> float:
        """Centre speed in body heights per second over the last `window` seconds."""
        if len(self.trail) < 2 or body_px <= 0:
            return 0.0
        t1, x1, y1 = self.trail[-1]
        old = next((p for p in self.trail if t1 - p[0] <= window), self.trail[0])
        dt = t1 - old[0]
        if dt < 0.2:
            return 0.0
        return float(np.hypot(x1 - old[1], y1 - old[2]) / dt / body_px)


class Tracker:
    def __init__(self, th: Thresholds):
        self.th = th
        self.tracks: list[Track] = []
        self._next_id = 1

    def update(self, t: float, dets: list[Detection]) -> tuple[list[Track], list[Track]]:
        """Returns (tracks seen this frame, tracks dropped this frame)."""
        th = self.th
        for tr in self.tracks:
            tr.matched_now = False
        if self.tracks and dets:
            cost = np.full((len(self.tracks), len(dets)), 1e6)
            for i, tr in enumerate(self.tracks):
                diag = float(np.hypot(tr.box[2] - tr.box[0], tr.box[3] - tr.box[1])) or 1.0
                for j, d in enumerate(dets):
                    ov = iou(tr.box, d.box)
                    dist = float(np.linalg.norm(centre(tr.box) - centre(d.box))) / diag
                    if ov >= th.track_iou:
                        cost[i, j] = 1.0 - ov
                    elif dist <= th.track_max_dist:
                        cost[i, j] = 1.0 + dist
            rows, cols = linear_sum_assignment(cost)
            matched_dets = set()
            for i, j in zip(rows, cols):
                if cost[i, j] < 1e5:
                    self._apply(self.tracks[i], dets[j], t)
                    matched_dets.add(j)
            new = [d for j, d in enumerate(dets) if j not in matched_dets]
        else:
            new = list(dets)
        for d in new:
            tr = Track(self._next_id, d.box, d.kpts, d.scores, born_t=t, last_t=t)
            tr.trail.append((t, *centre(d.box)))
            self.tracks.append(tr)
            self._next_id += 1

        dropped, keep = [], []
        for tr in self.tracks:
            on_ground = tr.machine is not None and tr.machine.state.value in (
                "FALL", "DOWN", "ALERT", "ESCALATED", "BEING_HELPED", "RESOLVED")
            limit = th.track_sticky_s if on_ground else th.track_lost_s
            if t - tr.last_t > limit:
                dropped.append(tr)
            elif tr.hits < th.track_min_hits and t - tr.last_t > 0.5:
                dropped.append(tr)
            else:
                keep.append(tr)
        self.tracks = keep
        seen = [tr for tr in self.tracks if tr.matched_now and tr.hits >= th.track_min_hits]
        return seen, dropped

    @staticmethod
    def _apply(tr: Track, d: Detection, t: float) -> None:
        tr.box, tr.kpts, tr.scores = d.box, d.kpts, d.scores
        tr.last_t = t
        tr.hits += 1
        tr.matched_now = True
        tr.trail.append((t, *centre(d.box)))
