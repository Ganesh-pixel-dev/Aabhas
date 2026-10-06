"""Multi-person pose from rtmlib (RTMPose + YOLOX, ONNX, CPU).

Licences: rtmlib is Apache-2.0. RTMPose and the YOLOX person detector (MMPose / MMDetection
model zoo, Megvii YOLOX) are Apache-2.0 code. The weights are trained on public datasets
(COCO, AI Challenger, CrowdPose and others) whose own terms differ, so check them before
selling a product built on these weights.
"""
from __future__ import annotations

import io
import contextlib
from dataclasses import dataclass

import numpy as np

# COCO-17 order
NOSE, L_SHO, R_SHO, L_HIP, R_HIP = 0, 5, 6, 11, 12
EDGES = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
         (11, 13), (13, 15), (12, 14), (14, 16), (0, 1), (0, 2), (1, 3), (2, 4)]
KPT_CONF = 0.3


@dataclass
class Detection:
    box: np.ndarray       # (4,) x1, y1, x2, y2
    kpts: np.ndarray      # (17, 2)
    scores: np.ndarray    # (17,)


class PoseEstimator:
    def __init__(self, mode: str = "balanced", min_box_h: float = 20.0):
        from rtmlib import Body
        with contextlib.redirect_stdout(io.StringIO()):
            self._body = Body(mode=mode, to_openpose=False, backend="onnxruntime", device="cpu")
        self.min_box_h = min_box_h

    def __call__(self, frame_bgr: np.ndarray) -> list[Detection]:
        boxes = self._body.det_model(frame_bgr)
        if boxes is None or len(boxes) == 0:
            return []
        kpts, scores = self._body.pose_model(frame_bgr, bboxes=boxes)
        out = []
        for b, k, s in zip(boxes, kpts, scores):
            if b[3] - b[1] >= self.min_box_h:
                out.append(Detection(np.asarray(b, dtype=np.float32), np.asarray(k, dtype=np.float32),
                                     np.asarray(s, dtype=np.float32)))
        return out


def torso_angle(kpts: np.ndarray, scores: np.ndarray) -> float | None:
    """Angle of the hip-to-shoulder line from vertical, degrees. 0 standing, 90 flat. None if unsure."""
    def mid(ids):
        pts = [kpts[i] for i in ids if scores[i] >= KPT_CONF]
        return np.mean(pts, axis=0) if pts else None
    sho, hip = mid((L_SHO, R_SHO)), mid((L_HIP, R_HIP))
    if sho is None or hip is None:
        return None
    dx, dy = abs(sho[0] - hip[0]), abs(sho[1] - hip[1])
    if dx + dy < 4:
        return None
    return float(np.degrees(np.arctan2(dx, dy)))
