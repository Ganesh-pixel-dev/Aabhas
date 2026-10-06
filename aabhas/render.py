"""Draw skeletons on a blank background. This is all the live tiles and the default replay show."""
from __future__ import annotations

import cv2
import numpy as np

from .fall_machine import ON_GROUND, State
from .pose import EDGES, KPT_CONF

BG = (22, 18, 16)          # BGR, near black
COLORS = {                 # BGR
    State.UPRIGHT: (200, 200, 196), State.RECOVERED: (140, 190, 90), State.LYING: (160, 160, 150),
    State.FALL: (40, 170, 245), State.DOWN: (40, 170, 245), State.BEING_HELPED: (200, 170, 70),
    State.ALERT: (60, 75, 255), State.ESCALATED: (60, 75, 255), State.RESOLVED: (150, 150, 150),
}


LYING_CONF = 0.12   # pose models are unsure about people on the ground, so draw what they give


def draw(size: tuple[int, int], people, label: str = "", min_width: int = 640) -> np.ndarray:
    """Skeletons on a dark canvas, scaled up so small frames still read."""
    w, h = size
    z = max(1.0, min_width / w)
    img = np.full((int(h * z), int(w * z), 3), BG, np.uint8)
    for p in people:
        col = COLORS.get(p.state, (200, 200, 200))
        thr = LYING_CONF if p.state in ON_GROUND else KPT_CONF
        k = np.array(p.kpts, np.float32) * z
        for a, b in EDGES:
            if p.scores[a] >= thr and p.scores[b] >= thr:
                cv2.line(img, tuple(int(v) for v in k[a]), tuple(int(v) for v in k[b]), col, 2, cv2.LINE_AA)
        for i in range(17):
            if p.scores[i] >= thr:
                cv2.circle(img, tuple(int(v) for v in k[i]), 3, col, -1, cv2.LINE_AA)
        x1, y1, x2, y2 = (int(v * z) for v in p.box)
        cv2.rectangle(img, (x1, y1), (x2, y2), col, 1)
        tag = f"#{p.id} {p.state.value}"
        if p.countdown is not None:
            tag += f" {p.countdown:0.0f}s"
        cv2.putText(img, tag, (x1, max(14, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
    if label:
        cv2.putText(img, label, (10, img.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 116), 1, cv2.LINE_AA)
    return img
