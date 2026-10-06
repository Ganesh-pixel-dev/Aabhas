"""Helpers that script a person's posture over time for the state machine tests."""
from aabhas.config import Thresholds
from aabhas.fall_machine import FallMachine, Obs, State

DT = 0.1
STAND = (100.0, 100.0, 140.0, 220.0)    # 40 x 120
LIE = (60.0, 190.0, 180.0, 225.0)       # 120 x 35
SIT = (100.0, 140.0, 150.0, 220.0)      # 50 x 80


def lerp(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


class Run:
    """Drives one FallMachine and remembers every transition."""

    def __init__(self, **overrides):
        self.th = Thresholds().with_overrides(overrides)
        self.m = FallMachine(self.th, t0=0.0)
        self.t = 0.0
        self.log: list = []

    def feed(self, box, angle, seconds, helper_s=0.0, seen=True):
        n = int(round(seconds / DT))
        for _ in range(n):
            self.t = round(self.t + DT, 3)
            obs = Obs(self.t, box, angle) if seen else None
            self.log += self.m.update(self.t, obs, helper_s)

    def move(self, a, b, angle_a, angle_b, seconds):
        n = max(int(round(seconds / DT)), 1)
        for i in range(1, n + 1):
            k = i / n
            self.t = round(self.t + DT, 3)
            self.log += self.m.update(self.t, Obs(self.t, lerp(a, b, k), angle_a + (angle_b - angle_a) * k))

    def states(self):
        return [tr.dst for tr in self.log]

    @property
    def state(self):
        return self.m.state


def standing_then_fall(**overrides):
    r = Run(**overrides)
    r.feed(STAND, 8, 3.0)
    r.move(STAND, LIE, 8, 85, 0.8)
    return r
