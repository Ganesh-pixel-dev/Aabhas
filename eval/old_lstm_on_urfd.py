"""Score the ORIGINAL MediaPipe + BiLSTM detector (kept in _old/) on the UR Fall clips.

The old model never saw this dataset, so all 70 sequences are held out for it.
A "Collapse" event is the first of >= 3 consecutive windows whose top class is Collapse
(Altercation is ignored). Same detection window and false-alarm rule as eval/score_urfd.py.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT / "_old"
sys.path.insert(0, str(OLD / "pydeps"))   # protobuf<5, which the old mediapipe needs
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(ROOT / "eval"))
from src.config import ACTIONS, FEATURE_DIM, HIDDEN_DIM, NUM_CLASSES, NUM_LAYERS, WINDOW_SIZE  # noqa: E402
from src.kinematics import calculate_kinematics  # noqa: E402
from src.model import BiLSTMActionRecognizer  # noqa: E402
from src.pose_extraction import PoseExtractor  # noqa: E402
from score_urfd import URFD, load_labels  # noqa: E402

model = BiLSTMActionRecognizer(FEATURE_DIM, HIDDEN_DIM, NUM_LAYERS, NUM_CLASSES)
model.load_state_dict(torch.load(OLD / "models" / "best_model.pth", map_location="cpu"))
model.eval()
pe = PoseExtractor()


def events_for(video: Path) -> tuple[list[float], float]:
    cap = cv2.VideoCapture(str(video))
    buf, preds, i = [], [], 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        i += 1
        lm, _ = pe.extract_pose(img[:, 320:])
        if lm is None:
            buf.clear()
            preds.append((i, None))
            continue
        buf.append(lm)
        buf[:] = buf[-WINDOW_SIZE:]
        if len(buf) == WINDOW_SIZE:
            x = torch.tensor(calculate_kinematics(np.array(buf)), dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                preds.append((i, ACTIONS[int(model(x).argmax(1))]))
        else:
            preds.append((i, None))
    times, run = [], 0
    for idx, p in preds:
        run = run + 1 if p == "Collapse" else 0
        if run == 3:
            times.append((idx - 1) / 30.0)
    return times, i / 30.0


def main() -> None:
    fall_labels = load_labels("urfall-cam0-falls.csv")
    det, delays, rows = 0, [], []
    for n in range(1, 31):
        name = f"fall-{n:02d}"
        lab = fall_labels[name]
        t_fall = (min(f for f, v in lab.items() if v == 0) - 1) / 30
        t_lie = (min(f for f, v in lab.items() if v == 1) - 1) / 30
        ev, _ = events_for(URFD / "falls" / f"{name}.mp4")
        hit = [t for t in ev if t_fall - 1.0 <= t <= t_lie + 3.0]
        det += bool(hit)
        if hit:
            delays.append(hit[0] - t_fall)
        rows.append((name, bool(hit)))
    false, secs = 0, 0.0
    for n in range(1, 41):
        ev, dur = events_for(URFD / "adl" / f"adl-{n:02d}.mp4")
        false += len(ev)
        secs += dur
    res = {"model": "old MediaPipe+BiLSTM (Collapse class)", "falls_detected": det, "falls_total": 30,
           "delay_median_s": round(float(np.median(delays)), 2) if delays else None,
           "adl_minutes": round(secs / 60, 1), "false_events": false,
           "false_per_hour": round(false / (secs / 3600), 1)}
    print(json.dumps(res, indent=1))
    (ROOT / "docs" / "results" / "urfd_old_bilstm.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
