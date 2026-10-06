"""Score the fall logic on the UR Fall Detection dataset (camera 0, RGB), event level.

Uses the pose cache from eval/extract_poses.py.

  falls:   a fall counts as detected if a FALL event fires between 1 s before the first
           "falling" frame and 3 s after the first "lying" frame. Delay is measured from
           the first "falling" frame.
  adl:     every FALL event on a non-fall sequence is a false alarm. DOWN and ALERT events
           are counted too.
  chain:   (synthetic) the last detections of each fall clip are repeated for 45 s so the
           DOWN -> ALERT path can run, since the real clips end a second or two after the fall.

    python eval/score_urfd.py --mode balanced
    python eval/score_urfd.py --mode balanced --th drop_frac=0.25 --split dev
"""
import argparse
import csv
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from aabhas.config import Thresholds  # noqa: E402
from aabhas.monitor import Monitor  # noqa: E402
from aabhas.pose import Detection  # noqa: E402

URFD = ROOT / "datasets" / "urfd"
# Odd-numbered sequences are for choosing thresholds, even-numbered ones are never looked at
# until the thresholds are fixed. (The ADL set is ordered by activity, so a front/back split
# would put every "lying on the floor" clip on one side.)
DEV = {"falls": range(1, 31, 2), "adl": range(1, 41, 2)}
TEST = {"falls": range(2, 31, 2), "adl": range(2, 41, 2)}


def load_labels(name: str) -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = defaultdict(dict)
    with open(URFD / name, newline="") as f:
        for row in csv.reader(f):
            out[row[0]][int(row[1])] = int(row[2])
    return out


def run_sequence(cache: dict, th: Thresholds, hold_s: float = 0.0):
    mon = Monitor("urfd", th)
    events = []
    fps = cache["fps"]
    last_t, last_dets = 0.0, []
    for idx, raw in cache["frames"]:
        t = (idx - 1) / fps
        dets = [Detection(b, k, s) for b, k, s in raw]
        events += mon.step(t, dets)
        last_t, last_dets = t, dets
    if hold_s:
        t = last_t
        while t < last_t + hold_s:
            t += 0.1
            events += mon.step(t, last_dets)
    return events, last_t


def pick(split: str):
    if split == "dev":
        return DEV
    if split == "test":
        return TEST
    return {"falls": range(1, 31), "adl": range(1, 41)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="balanced")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="all")
    ap.add_argument("--th", nargs="*", default=[], help="threshold overrides, e.g. drop_frac=0.25")
    ap.add_argument("--json", help="write results here")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    overrides = {}
    for kv in args.th:
        k, v = kv.split("=")
        overrides[k] = float(v)
    th = Thresholds().with_overrides(overrides)
    seqs = pick(args.split)
    cache_dir = URFD / f"poses_{args.mode}"
    fall_labels, adl_labels = load_labels("urfall-cam0-falls.csv"), load_labels("urfall-cam0-adls.csv")

    detected, delays, rows = 0, [], []
    for i in seqs["falls"]:
        name = f"fall-{i:02d}"
        lab = fall_labels[name]
        f_fall = min(f for f, v in lab.items() if v == 0)
        f_lying = min(f for f, v in lab.items() if v == 1)
        fps = 30.0
        cache = pickle.load(open(cache_dir / f"{name}.pkl", "rb"))
        events, dur = run_sequence(cache, th)
        t_fall, t_lying = (f_fall - 1) / fps, (f_lying - 1) / fps
        hits = [e for e in events if e.type == "FALL" and t_fall - 1.0 <= e.t <= t_lying + 3.0]
        late = [e for e in events if e.type == "FALL"]
        ok = bool(hits)
        detected += ok
        if ok:
            delays.append(hits[0].t - t_fall)
        chain_events, _ = run_sequence(cache, th, hold_s=45.0)
        chain_alert = any(e.type == "ALERT" for e in chain_events)
        rows.append({"seq": name, "detected": ok, "delay_s": round(hits[0].t - t_fall, 2) if ok else None,
                     "any_fall_events": len(late), "chain_alert_after_hold": chain_alert, "video_s": round(dur, 1)})

    adl_seconds, false_fall, false_down, false_alert, fa_seqs = 0.0, 0, 0, 0, []
    for i in seqs["adl"]:
        name = f"adl-{i:02d}"
        cache = pickle.load(open(cache_dir / f"{name}.pkl", "rb"))
        events, dur = run_sequence(cache, th)
        adl_seconds += cache["n_frames"] / cache["fps"]
        n = sum(e.type == "FALL" for e in events)
        false_fall += n
        false_down += sum(e.type == "DOWN" for e in events)
        false_alert += sum(e.type == "ALERT" for e in events)
        if n:
            fa_seqs.append((name, n))

    n_falls = len(seqs["falls"])
    chain_ok = sum(r["chain_alert_after_hold"] for r in rows)
    res = {
        "mode": args.mode, "split": args.split, "overrides": overrides,
        "falls_total": n_falls, "falls_detected": detected,
        "delay_median_s": round(float(np.median(delays)), 2) if delays else None,
        "delay_max_s": round(float(np.max(delays)), 2) if delays else None,
        "adl_sequences": len(seqs["adl"]), "adl_minutes": round(adl_seconds / 60, 1),
        "false_fall_events": false_fall, "false_down_events": false_down, "false_alert_events": false_alert,
        "false_fall_per_hour": round(false_fall / (adl_seconds / 3600), 1) if adl_seconds else None,
        "false_fall_sequences": fa_seqs,
        "chain_synthetic_alerts": f"{chain_ok}/{n_falls}",
    }
    if not args.quiet:
        for r in rows:
            print(r)
    print(json.dumps(res, indent=1))
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": res, "falls": rows}, indent=1))


if __name__ == "__main__":
    main()
