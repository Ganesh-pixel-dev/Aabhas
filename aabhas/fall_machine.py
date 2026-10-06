"""Per-person fall state machine. Pure logic: no video, no clock, no I/O.

    UPRIGHT -> FALL          fast drop of the body centre while the torso goes flat
    FALL -> DOWN             still not upright settle_s after the drop
    DOWN -> ALERT            down_seconds after the fall began and nobody stopped nearby
    ALERT -> ESCALATED       nobody acknowledged the alert in time
    DOWN/ALERT/ESCALATED -> BEING_HELPED   someone else stopped next to them
    any ground state -> RECOVERED          the person stands up (log only, no alert)
    UPRIGHT -> LYING         low for lying_s with no fall before it (sleeping): never alerts

All times come from the `t` you pass in, so tests can script a sequence by hand.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .config import Thresholds


class State(str, Enum):
    UPRIGHT = "UPRIGHT"
    FALL = "FALL"
    DOWN = "DOWN"
    ALERT = "ALERT"
    ESCALATED = "ESCALATED"
    BEING_HELPED = "BEING_HELPED"
    RECOVERED = "RECOVERED"
    LYING = "LYING"
    RESOLVED = "RESOLVED"        # operator marked a false alarm; quiet until the person stands


ALERTING = (State.ALERT, State.ESCALATED)
ON_GROUND = (State.FALL, State.DOWN, State.ALERT, State.ESCALATED, State.BEING_HELPED, State.RESOLVED)


@dataclass
class Obs:
    """One detection of one person in one frame."""
    t: float
    box: tuple[float, float, float, float]    # x1, y1, x2, y2 in pixels
    angle: Optional[float] = None             # torso angle from vertical, degrees; None if unknown


@dataclass
class Transition:
    t: float
    src: State
    dst: State
    reason: str
    info: dict = field(default_factory=dict)


@dataclass
class _Sample:
    t: float
    cy: float
    angle: Optional[float]
    h_ratio: float
    aspect: float


class FallMachine:
    def __init__(self, th: Thresholds, t0: float = 0.0):
        self.th = th
        self.t0 = t0
        self.state = State.UPRIGHT
        self.fall_t: Optional[float] = None      # when the drop started
        self.alert_t: Optional[float] = None
        self.acknowledged = False
        self.dispatched = False
        self.ref_h: Optional[float] = None       # standing height in pixels
        self.last_cy = 0.0
        self._hist: deque[_Sample] = deque()
        self._up_since: Optional[float] = None
        self._low_since: Optional[float] = None
        self._helper_gone_since: Optional[float] = None
        self._recovered_t: Optional[float] = None
        self._trigger_t: Optional[float] = None

    # ---- posture classification -------------------------------------------------
    def _upright(self, s: _Sample) -> bool:
        th = self.th
        ok = s.angle <= th.upright_angle_deg if s.angle is not None else s.aspect < 0.8
        return ok and s.h_ratio >= th.upright_height_ratio

    def _low(self, s: _Sample) -> bool:
        th = self.th
        if s.angle is not None and s.angle >= th.horizontal_angle_deg:
            return True
        return s.aspect >= 1.0 and s.h_ratio <= th.low_height_ratio

    # ---- operator actions ---------------------------------------------------------
    def acknowledge(self) -> None:
        self.acknowledged = True

    def dispatch(self) -> None:
        self.acknowledged = True
        self.dispatched = True

    def false_alarm(self, t: float) -> list[Transition]:
        if self.state in ALERTING + (State.DOWN, State.BEING_HELPED):
            return [self._go(t, State.RESOLVED, "operator: false alarm")]
        return []

    # ---- main entry ---------------------------------------------------------------
    def update(self, t: float, obs: Optional[Obs], helper_s: float = 0.0) -> list[Transition]:
        """Advance to time t. obs is None when the person was not seen this frame.
        helper_s is how long someone else has stood still near this person."""
        sample = self._ingest(t, obs)
        if sample is not None:
            up = self._upright(sample)
            low = self._low(sample)
            self._up_since = (self._up_since if self._up_since is not None else t) if up else None
            self._low_since = (self._low_since if self._low_since is not None else t) if low else None
        upright_run = (t - self._up_since) if self._up_since is not None else 0.0

        if helper_s > 0:
            self._helper_gone_since = None
        elif self._helper_gone_since is None:
            self._helper_gone_since = t

        out: list[Transition] = []
        for _ in range(4):   # one state can hand straight on to the next
            tr = self._step(t, sample, upright_run, helper_s)
            if tr is None:
                break
            out.append(tr)
        return out

    def _ingest(self, t: float, obs: Optional[Obs]) -> Optional[_Sample]:
        if obs is None:
            return None
        x1, y1, x2, y2 = obs.box
        w, h = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
        if self.ref_h is None:
            self.ref_h = h if w / h < 0.8 else max(w, h)
        s = _Sample(t=t, cy=(y1 + y2) / 2, angle=obs.angle, h_ratio=h / self.ref_h, aspect=w / h)
        self.last_cy = s.cy
        if self.state in (State.UPRIGHT, State.RECOVERED) and self._upright(s):
            self.ref_h = 0.9 * self.ref_h + 0.1 * h
            s.h_ratio = h / self.ref_h
        self._hist.append(s)
        keep = max(self.th.fall_window_s, 1.0) + 0.5
        while self._hist and t - self._hist[0].t > keep:
            self._hist.popleft()
        return s

    def _go(self, t: float, dst: State, reason: str, **info) -> Transition:
        tr = Transition(t, self.state, dst, reason, info)
        self.state = dst
        return tr

    def _step(self, t: float, s: Optional[_Sample], upright_run: float, helper_s: float) -> Optional[Transition]:
        th, st = self.th, self.state

        if st in (State.UPRIGHT, State.RECOVERED):
            if st == State.RECOVERED and self._recovered_t is not None and t - self._recovered_t >= th.recovered_hold_s:
                self.state = State.UPRIGHT
            if s is not None and self._fall_triggered(t, s):
                return self._go(t, State.FALL, "fast drop, torso flat", fall_t=self.fall_t)
            if (s is not None and self.state == State.UPRIGHT and self._low_since is not None
                    and t - self._low_since >= th.lying_s):
                return self._go(t, State.LYING, "low with no fall before it")
            return None

        if st == State.LYING:
            if upright_run >= th.getup_s:
                self.state = State.UPRIGHT
            return None

        if st in ON_GROUND and upright_run >= th.getup_s:
            return self._recovered(t)

        if st == State.FALL:
            if t - (self._trigger_t or t) >= th.settle_s and self._up_since is None:
                return self._go(t, State.DOWN, "still down after the fall")
            return None

        if st == State.DOWN:
            if helper_s >= th.help_dwell_s:
                return self._go(t, State.BEING_HELPED, "someone stopped nearby", helper_s=helper_s)
            if t - (self.fall_t or t) >= th.down_seconds:
                self.alert_t = t
                self.acknowledged = self.dispatched = False
                return self._go(t, State.ALERT, f"down {th.down_seconds:g}s, nobody stopped nearby")
            return None

        if st == State.BEING_HELPED:
            gone = self._helper_gone_since
            if gone is not None and t - gone >= th.help_leave_s:
                return self._go(t, State.DOWN, "helper left")
            return None

        if st in ALERTING:
            if helper_s >= th.help_dwell_s:
                return self._go(t, State.BEING_HELPED, "someone stopped nearby", helper_s=helper_s)
            if (st == State.ALERT and not self.acknowledged and self.alert_t is not None
                    and t - self.alert_t >= th.escalate_after_s):
                return self._go(t, State.ESCALATED, "not acknowledged in time")
            return None

        return None   # RESOLVED waits for the person to stand

    def _recovered(self, t: float) -> Transition:
        down_for = t - self.fall_t if self.fall_t is not None else None
        tr = self._go(t, State.RECOVERED, "person stood up", down_for=down_for)
        self._recovered_t = t
        self.fall_t = None
        self._trigger_t = None
        self.acknowledged = self.dispatched = False
        return tr

    # ---- the trigger ---------------------------------------------------------------
    def _fall_triggered(self, t: float, now: _Sample) -> bool:
        th = self.th
        if t - self.t0 < th.min_track_age_s or self.ref_h is None:
            return False
        win = [x for x in self._hist if t - x.t <= th.fall_window_s]
        if len(win) < 3 or not self._low(now):
            return False
        ups = [x for x in win if x is not now and self._upright(x)]
        if not ups:
            return False
        pre = min(ups, key=lambda x: x.cy)
        if (now.cy - pre.cy) / self.ref_h < th.drop_frac:
            return False
        if self._peak_speed(win) < th.min_peak_speed:
            return False
        top = min(x.cy for x in win)
        self.fall_t = max(x.t for x in win if x.cy <= top + 0.05 * self.ref_h and x.t < now.t)
        self._trigger_t = t
        return True

    def _peak_speed(self, win: list[_Sample]) -> float:
        best = 0.0
        for i, b in enumerate(win):
            for a in win[:i]:
                dt = b.t - a.t
                if 0.1 <= dt <= 0.4:
                    best = max(best, (b.cy - a.cy) / self.ref_h / dt)
        return best
