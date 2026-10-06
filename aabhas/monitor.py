"""One camera's logic: detections in, events out.

Ties the tracker to one FallMachine per person and works out who counts as help.
It never touches video frames, only detections, so the same code runs live, in the
evaluation scripts and in tests.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .config import Thresholds
from .fall_machine import ALERTING, ON_GROUND, FallMachine, Obs, State, Transition
from .pose import Detection, torso_angle
from .tracking import Track, Tracker, centre

FALLEN = (State.FALL, State.DOWN, State.ALERT, State.ESCALATED, State.BEING_HELPED)


@dataclass
class Event:
    t: float
    camera: str
    track: int
    type: str                 # a State name, or LOST
    reason: str = ""
    info: dict = field(default_factory=dict)


@dataclass
class PersonView:
    id: int
    state: State
    box: list[float]
    kpts: list[list[float]]
    scores: list[float]
    countdown: Optional[float] = None     # seconds until an alert, while FALL/DOWN
    down_for: Optional[float] = None
    acknowledged: bool = False


@dataclass
class Snap:
    t: float
    people: list[PersonView]


class Monitor:
    def __init__(self, camera: str, th: Thresholds, replay_seconds: float = 25.0):
        self.camera = camera
        self.th = th
        self.tracker = Tracker(th)
        self.replay: deque[Snap] = deque()
        self.replay_seconds = replay_seconds
        self.people: list[PersonView] = []
        self.t = 0.0
        self._dwell: dict[tuple[int, int], tuple[float, float]] = {}   # (fallen, other) -> (stopped_since, last_ok_t)

    # ---- per frame ---------------------------------------------------------------
    def step(self, t: float, dets: list[Detection]) -> list[Event]:
        th = self.th
        self.t = t
        seen, dropped = self.tracker.update(t, dets)
        events: list[Event] = []

        for tr in seen:
            if tr.machine is None:
                tr.machine = FallMachine(th, t0=tr.born_t)

        helper = self._helper_seconds(t, seen)
        seen_ids = {tr.id for tr in seen}
        for tr in self.tracker.tracks:
            if tr.machine is None:
                continue
            obs = None
            if tr.id in seen_ids:
                obs = Obs(t, tuple(float(v) for v in tr.box), torso_angle(tr.kpts, tr.scores))
            trs = tr.machine.update(t, obs, helper.get(tr.id, 0.0))
            events += [self._event(tr, x) for x in trs]

        for tr in dropped:
            if tr.machine is not None and tr.machine.state in ON_GROUND:
                events.append(Event(t, self.camera, tr.id, "LOST",
                                    f"track lost while {tr.machine.state.value}", {"was": tr.machine.state.value}))

        self.people = [self._view(t, tr) for tr in self.tracker.tracks
                       if tr.id in seen_ids or (tr.machine and tr.machine.state in ON_GROUND)]
        self.replay.append(Snap(t, self.people))
        while self.replay and t - self.replay[0].t > self.replay_seconds:
            self.replay.popleft()
        return events

    def _event(self, tr: Track, x: Transition) -> Event:
        info = dict(x.info)
        info["box"] = [round(float(v), 1) for v in tr.box]
        if tr.machine is not None and tr.machine.fall_t is not None:
            info.setdefault("fall_t", tr.machine.fall_t)
        return Event(x.t, self.camera, tr.id, x.dst.value, x.reason, info)

    def _view(self, t: float, tr: Track) -> PersonView:
        m = tr.machine
        countdown = down_for = None
        if m is not None and m.state in (State.FALL, State.DOWN) and m.fall_t is not None:
            countdown = max(0.0, self.th.down_seconds - (t - m.fall_t))
        if m is not None and m.state in FALLEN and m.fall_t is not None:
            down_for = t - m.fall_t
        return PersonView(
            id=tr.id, state=m.state if m else State.UPRIGHT,
            box=[round(float(v), 1) for v in tr.box],
            kpts=[[round(float(a), 1), round(float(b), 1)] for a, b in tr.kpts],
            scores=[round(float(s), 2) for s in tr.scores],
            countdown=countdown, down_for=down_for,
            acknowledged=bool(m and m.acknowledged),
        )

    # ---- who counts as help ------------------------------------------------------
    def _helper_seconds(self, t: float, seen: list[Track]) -> dict[int, float]:
        th = self.th
        out: dict[int, float] = {}
        fallen = [tr for tr in self.tracker.tracks if tr.machine and tr.machine.state in FALLEN]
        live = {(f.id, o.id) for f in fallen for o in seen}
        self._dwell = {k: v for k, v in self._dwell.items() if k in live}
        for f in fallen:
            body = f.machine.ref_h or float(f.box[3] - f.box[1])
            fc = centre(f.box)
            best = 0.0
            for o in seen:
                if o.id == f.id or o.machine is None or o.machine.state in ON_GROUND + (State.LYING,):
                    continue
                obody = o.machine.ref_h or float(o.box[3] - o.box[1])
                near = np.linalg.norm(centre(o.box) - fc) <= th.help_radius * body
                still = o.speed(obody) <= th.help_still_speed
                key = (f.id, o.id)
                start, last_ok = self._dwell.get(key, (t, -1e9))
                if near and still:
                    if t - last_ok > 1.0:
                        start = t           # they only just stopped (or came back after a gap)
                    self._dwell[key] = (start, t)
                    best = max(best, t - start)
                elif t - last_ok <= 1.0:
                    best = max(best, last_ok - start)   # brief wobble, keep the dwell so far
            out[f.id] = best
        return out

    # ---- operator actions, forwarded to the machine ---------------------------------
    def _machine(self, track: int) -> Optional[FallMachine]:
        for tr in self.tracker.tracks:
            if tr.id == track:
                return tr.machine
        return None

    def acknowledge(self, track: int) -> None:
        m = self._machine(track)
        if m:
            m.acknowledge()

    def dispatch(self, track: int) -> None:
        m = self._machine(track)
        if m:
            m.dispatch()

    def false_alarm(self, track: int) -> list[Event]:
        m = self._machine(track)
        if not m:
            return []
        return [Event(x.t, self.camera, track, x.dst.value, x.reason) for x in m.false_alarm(self.t)]

    # ---- skeleton replay ----------------------------------------------------------
    def skeleton_replay(self, subject: int, since: float) -> dict:
        frames = []
        for s in self.replay:
            if s.t < since:
                continue
            frames.append({
                "t": round(s.t, 2),
                "people": [{"id": p.id, "subject": p.id == subject, "state": p.state.value,
                            "box": p.box, "kpts": p.kpts, "scores": p.scores} for p in s.people],
            })
        return {"subject": subject, "frames": frames}
