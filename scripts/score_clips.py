"""Score Aabhas on clips you filmed yourself. Protocol: docs/STAGED-FALLS.md.

    python scripts/score_clips.py --clips my_clips --labels my_clips/labels.csv [--config config/cameras.yaml --camera cam1]

labels.csv columns:  file, scenario, fall_start_s
  scenario is one of: fall_no_help, fall_help, fall_getup, lying_no_fall, sitting, shoelaces, crowd_walk, other_none
  fall_start_s is when the person's feet leave the floor / the drop begins (leave empty for no-fall clips)

What each scenario must produce (this is the expected outcome, the script checks it):
  fall_no_help   FALL then ALERT (after down_seconds)
  fall_help      FALL, then BEING_HELPED, and no ALERT
  fall_getup     FALL, then RECOVERED, and no ALERT
  everything else  no FALL and no ALERT at all
"""
import argparse
import csv
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from aabhas.config import Thresholds, load_settings  # noqa: E402
from aabhas.monitor import Monitor  # noqa: E402
from aabhas.pose import PoseEstimator  # noqa: E402

EXPECT = {
    "fall_no_help": ({"FALL", "ALERT"}, set()),
    "fall_help": ({"FALL", "BEING_HELPED"}, {"ALERT"}),
    "fall_getup": ({"FALL", "RECOVERED"}, {"ALERT"}),
}


def run_clip(path: Path, th: Thresholds, pose: PoseEstimator, crop=None, fps_limit: float = 10.0):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / fps_limit))
    mon, events, i = Monitor("clip", th), [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if (i - 1) % step:
            continue
        if crop:
            x, y, w, h = crop
            frame = frame[y:y + h, x:x + w]
        events += mon.step((i - 1) / fps, pose(frame))
    return events, i / fps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--config")
    ap.add_argument("--camera")
    ap.add_argument("--mode", default="balanced")
    ap.add_argument("--crop", help="x,y,w,h to cut out of every frame")
    args = ap.parse_args()

    th = Thresholds()
    if args.config:
        cams = {c.id: c for c in load_settings(args.config).cameras}
        th = cams[args.camera or next(iter(cams))].thresholds
    pose = PoseEstimator(args.mode)
    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None

    rows, ok_n, falls_n, delays, bad_secs, bad_alerts, quiet_secs = [], 0, 0, [], 0.0, 0, 0.0
    for r in csv.DictReader(open(args.labels, newline="")):
        ev, dur = run_clip(Path(args.clips) / r["file"], th, pose, crop)
        got = {e.type for e in ev}
        want, forbid = EXPECT.get(r["scenario"], (set(), {"FALL", "ALERT"}))
        passed = want <= got and not (forbid & got)
        delay = None
        if r["scenario"] in EXPECT:
            falls_n += 1
            first = next((e.t for e in ev if e.type == "FALL"), None)
            if first is not None and r.get("fall_start_s"):
                delay = first - float(r["fall_start_s"])
                delays.append(delay)
        else:
            quiet_secs += dur
            bad_alerts += sum(e.type in ("FALL", "ALERT") for e in ev)
        ok_n += passed
        rows.append((r["file"], r["scenario"], "PASS" if passed else "FAIL", sorted(got), None if delay is None else round(delay, 2)))
    for row in rows:
        print(*row, sep="  ")
    print(f"\nclips passed: {ok_n}/{len(rows)}")
    print(f"fall clips: {falls_n}; median detection delay: {sorted(delays)[len(delays) // 2]:.2f}s" if delays else f"fall clips: {falls_n}")
    if quiet_secs:
        print(f"false FALL/ALERT events on no-fall clips: {bad_alerts} in {quiet_secs / 60:.1f} min "
              f"({bad_alerts / (quiet_secs / 3600):.1f} per hour; only meaningful with a lot of footage)")


if __name__ == "__main__":
    main()
