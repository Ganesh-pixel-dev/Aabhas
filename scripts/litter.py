"""EXPERIMENTAL littering hotspots. Only tested on synthetic frames, never on real footage.

    python scripts/litter.py scan --video clip.mp4 --camera gate1 --place "Campus gate" --start "2026-10-06 09:00"
    python scripts/litter.py report            # writes runtime/litter/hotspots.csv and hotspots.png

`scan` appends one row per event to runtime/litter/events.csv (camera, place, time, x, y).
`report` counts events per camera, place and hour of day. Open the CSV in a spreadsheet.
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from aabhas.litter import LitterDetector, hotspot_rows, write_csv  # noqa: E402

OUT = ROOT / "runtime" / "litter"


def scan(a) -> None:
    from aabhas.pose import PoseEstimator
    pose = PoseEstimator(a.mode)
    det = LitterDetector()
    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / 5))
    start = datetime.fromisoformat(a.start)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "events.csv"
    new = not path.exists()
    n = i = 0
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["camera", "place", "time", "hour", "x", "y"])
        while True:
            ok, img = cap.read()
            if not ok:
                break
            i += 1
            if (i - 1) % step:
                continue
            t = (i - 1) / fps
            for e in det.update(t, img, [d.box for d in pose(img)]):
                when = start + timedelta(seconds=e.t)
                w.writerow([a.camera, a.place, when.isoformat(timespec="seconds"), when.hour, round(e.x, 3), round(e.y, 3)])
                n += 1
    print(f"{n} events written to {path}")


def report(_a) -> None:
    path = OUT / "events.csv"
    if not path.exists():
        sys.exit("No events yet. Run scan first.")
    events = list(csv.DictReader(open(path, newline="")))
    rows = hotspot_rows(events)
    write_csv(rows, OUT / "hotspots.csv")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    places = sorted({r["place"] for r in rows})
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bottom = [0] * 24
    for pl in places:
        vals = [sum(r["count"] for r in rows if r["place"] == pl and r["hour"] == h) for h in range(24)]
        ax.bar(range(24), vals, bottom=bottom, label=pl)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xlabel("hour of day")
    ax.set_ylabel("events")
    ax.set_title("Possible littering events (experimental)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "hotspots.png", dpi=140)
    print("wrote", OUT / "hotspots.csv", "and", OUT / "hotspots.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(required=True)
    s = sub.add_parser("scan")
    s.add_argument("--video", required=True)
    s.add_argument("--camera", required=True)
    s.add_argument("--place", required=True)
    s.add_argument("--start", required=True, help="wall-clock time of the first frame, ISO format")
    s.add_argument("--mode", default="balanced")
    s.set_defaults(fn=scan)
    r = sub.add_parser("report")
    r.set_defaults(fn=report)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
