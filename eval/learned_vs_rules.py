"""Could a learned fall trigger beat the rules? Train a small BiLSTM on RTMPose keypoints of the
odd-numbered UR Fall sequences, score it on the even-numbered ones, same event rules as the
rule-based scorer. 15 fall sequences is very little training data; that is part of the answer.

    python eval/learned_vs_rules.py
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT))
from score_urfd import URFD, load_labels  # noqa: E402

WIN = 15          # 1.5 s at 10 fps
CACHE = URFD / "poses_balanced"


def feats(cache) -> tuple[np.ndarray, list[int]]:
    """One feature row per cached frame, for the biggest person in view."""
    rows, idxs, ref = [], [], None
    for idx, dets in cache["frames"]:
        if not dets:
            rows.append(np.zeros(38, np.float32) if not rows else rows[-1]); idxs.append(idx); continue
        b, k, s = max(dets, key=lambda d: (d[0][2] - d[0][0]) * (d[0][3] - d[0][1]))
        w, h = b[2] - b[0], b[3] - b[1]
        ref = ref or max(h, 1.0)
        c = np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2])
        rel = (k - c) / ref * (s[:, None] > 0.3)
        rows.append(np.concatenate([rel.ravel(), [w / ref, h / ref, c[1] / ref - 1.0, w / max(h, 1.0)]]).astype(np.float32))
        idxs.append(idx)
    return np.array(rows), idxs


def windows(name, kind, labels):
    cache = pickle.load(open(CACHE / f"{name}.pkl", "rb"))
    x, idxs = feats(cache)
    xs, ys, ends = [], [], []
    for e in range(WIN - 1, len(x)):
        xs.append(x[e - WIN + 1:e + 1])
        y = 0
        if kind == "falls":
            first = labels[name].get(idxs[e - WIN + 1], -1)
            last = labels[name].get(idxs[e], -1)
            y = int(first == -1 and last in (0, 1))
        ys.append(y)
        ends.append((idxs[e] - 1) / 30.0)
    return np.array(xs), np.array(ys), np.array(ends)


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.rnn = nn.LSTM(38, 32, 2, batch_first=True, bidirectional=True)
        self.out = nn.Linear(64, 1)

    def forward(self, x):
        return self.out(self.rnn(x)[0][:, -1]).squeeze(-1)


def main() -> None:
    fl, al = load_labels("urfall-cam0-falls.csv"), load_labels("urfall-cam0-adls.csv")
    data = {}
    for n in range(1, 31):
        data[f"fall-{n:02d}"] = ("falls", *windows(f"fall-{n:02d}", "falls", fl))
    for n in range(1, 41):
        data[f"adl-{n:02d}"] = ("adl", *windows(f"adl-{n:02d}", "adl", al))
    train = [k for k in data if int(k[-2:]) % 2 == 1]
    test = [k for k in data if int(k[-2:]) % 2 == 0]
    X = torch.tensor(np.concatenate([data[k][1] for k in train]))
    Y = torch.tensor(np.concatenate([data[k][2] for k in train]), dtype=torch.float32)
    results = []
    for seed in range(5):
        torch.manual_seed(seed)
        net = Net()
        opt = torch.optim.Adam(net.parameters(), 2e-3)
        lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(5.0))
        for _ in range(60):
            perm = torch.randperm(len(X))
            for i in range(0, len(X), 64):
                b = perm[i:i + 64]
                opt.zero_grad()
                lossf(net(X[b]), Y[b]).backward()
                opt.step()
        net.eval()
        det, delays, false, secs = 0, [], 0, 0.0
        for k in test:
            kind, xs, ys, ends = data[k]
            with torch.no_grad():
                p = (torch.sigmoid(net(torch.tensor(xs))) > 0.5).numpy()
            ev, run = [], 0
            for t, v in zip(ends, p):
                run = run + 1 if v else 0
                if run == 2:
                    ev.append(t)
            if kind == "falls":
                lab = fl[k]
                t_fall = (min(f for f, v in lab.items() if v == 0) - 1) / 30
                t_lie = (min(f for f, v in lab.items() if v == 1) - 1) / 30
                hit = [t for t in ev if t_fall - 1.0 <= t <= t_lie + 3.0]
                det += bool(hit)
                if hit:
                    delays.append(hit[0] - t_fall)
            else:
                false += len(ev)
                secs += len(xs) * 0.1
        results.append({"seed": seed, "falls_detected": det, "of": sum(data[k][0] == "falls" for k in test),
                        "false_events": false, "adl_minutes": round(secs / 60, 1),
                        "delay_median_s": round(float(np.median(delays)), 2) if delays else None})
        print(results[-1], flush=True)
    Path(ROOT / "docs" / "results" / "urfd_learned_bilstm.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
