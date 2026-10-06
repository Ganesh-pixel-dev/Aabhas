"""Scripted multi-person scenes through tracker + machines + help logic. Poses are synthetic."""
import numpy as np

from aabhas.config import Thresholds
from aabhas.monitor import Monitor
from aabhas.pose import Detection


def person(cx, foot_y, lying=False, h=120.0):
    """A skeleton-ish detection. Standing: tall box. Lying: wide, flat box."""
    k = np.zeros((17, 2), np.float32)
    if not lying:
        top = foot_y - h
        k[5], k[6] = (cx - 12, top + 0.2 * h), (cx + 12, top + 0.2 * h)
        k[11], k[12] = (cx - 8, top + 0.55 * h), (cx + 8, top + 0.55 * h)
        box = np.array([cx - 22, top, cx + 22, foot_y], np.float32)
    else:
        k[5], k[6] = (cx - 0.3 * h, foot_y - 12), (cx - 0.3 * h, foot_y - 4)
        k[11], k[12] = (cx + 0.05 * h, foot_y - 12), (cx + 0.05 * h, foot_y - 4)
        box = np.array([cx - 0.55 * h, foot_y - 28, cx + 0.55 * h, foot_y], np.float32)
    return Detection(box, k, np.full(17, 0.9, np.float32))


def run(th, seconds_script):
    """seconds_script: list of (t, [detections])"""
    m = Monitor("test", th)
    ev = []
    for t, dets in seconds_script:
        ev += m.step(t, dets)
    return m, ev


def timeline(fall_at=3.0, down_for=40.0, others=lambda t: [], lie_x=300.0):
    out, t = [], 0.0
    while t < fall_at + down_for:
        if t < fall_at:
            dets = [person(lie_x, 300)]
        elif t < fall_at + 0.6:
            k = (t - fall_at) / 0.6
            dets = [person(lie_x, 300, lying=k > 0.6, h=120 * (1 - 0.5 * k))]
        else:
            dets = [person(lie_x, 300, lying=True)]
        out.append((round(t, 2), dets + others(t)))
        t += 0.1
    return out


def types(ev):
    return [e.type for e in ev]


def test_lone_fall_ends_in_alert():
    m, ev = run(Thresholds(), timeline())
    assert types(ev) == ["FALL", "DOWN", "ALERT"]


def test_passerby_walking_past_is_not_help():
    walker = lambda t: [person(100 + 60 * t, 300)] if t > 2 else []   # keeps walking right
    m, ev = run(Thresholds(), timeline(others=walker))
    assert "ALERT" in types(ev) and "BEING_HELPED" not in types(ev)


def test_someone_who_stops_next_to_them_counts_as_help():
    def helper(t):
        if t < 8:
            return [person(520 - 28 * (t - 3), 300)] if t > 3 else []
        return [person(380, 300)]                     # stands still ~80 px away (under 1.5 body heights)
    m, ev = run(Thresholds(), timeline(others=helper))
    assert "BEING_HELPED" in types(ev) and "ALERT" not in types(ev)


def test_someone_stopped_far_away_is_not_help():
    far = lambda t: [person(30, 300)]
    m, ev = run(Thresholds(), timeline(others=far))
    assert "ALERT" in types(ev)


def test_fall_ids_are_stable_while_person_is_down():
    m, ev = run(Thresholds(), timeline())
    assert {e.track for e in ev} == {1}


def test_track_that_vanishes_while_down_is_kept_and_still_alerts():
    script = timeline(down_for=6.0)
    last = script[-1][0]
    t = last
    while t < last + 40:
        t = round(t + 0.1, 2)
        script.append((t, []))
    m, ev = run(Thresholds(), script)
    assert "ALERT" in types(ev)


def test_sleeping_person_never_alerts():
    script, t = [], 0.0
    while t < 600:
        script.append((round(t, 1), [person(300, 300, lying=True)]))
        t += 0.5
    m, ev = run(Thresholds(), script)
    assert "ALERT" not in types(ev) and "FALL" not in types(ev)


def test_skeleton_replay_has_no_pixels_only_points():
    m, ev = run(Thresholds(), timeline(down_for=5))
    rep = m.skeleton_replay(1, since=0)
    assert rep["frames"] and set(rep["frames"][-1]["people"][0]) == {"id", "subject", "state", "box", "kpts", "scores"}
