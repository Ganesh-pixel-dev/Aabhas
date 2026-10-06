import numpy as np

from aabhas.litter import LitterDetector, LitterParams, hotspot_rows

W, H = 320, 240


def scene(person_x=None, obj=False, noise=0):
    f = np.full((H, W, 3), 120, np.uint8)
    f[:, :, 1] += np.tile(np.linspace(0, 20, W, dtype=np.uint8), (H, 1))
    if obj:
        f[200:214, 150:166] = 30
    if person_x is not None:
        f[80:200, person_x:person_x + 30] = 200
    return f


def run(drops_object, person_near):
    det = LitterDetector(LitterParams(static_s=10, warmup_s=5, tau_fast_s=3))
    events = []
    t = 0.0
    while t < 60:
        t = round(t + 0.5, 1)
        placed = drops_object and t >= 20
        px = None
        boxes = []
        if person_near and 18 <= t <= 22:
            px = 135
            boxes = [(135, 80, 165, 200)]
        events += det.update(t, scene(px, placed), boxes)
    return events


def test_object_dropped_next_to_a_person_is_logged_once():
    ev = run(True, True)
    assert len(ev) == 1 and 0.4 < ev[0].x < 0.6 and ev[0].y > 0.8


def test_object_appearing_with_nobody_near_is_ignored():
    assert run(True, False) == []


def test_empty_scene_logs_nothing():
    assert run(False, True) == []


def test_hotspot_counts():
    rows = hotspot_rows([{"camera": "a", "place": "gate", "hour": 9}] * 3 + [{"camera": "a", "place": "gate", "hour": 10}])
    assert rows == [{"camera": "a", "place": "gate", "hour": 9, "count": 3}, {"camera": "a", "place": "gate", "hour": 10, "count": 1}]
