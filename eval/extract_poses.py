"""Run pose estimation once over the UR Fall videos and cache it, so thresholds can be
re-scored in seconds. Frames are subsampled to 10 fps, which is what the live pipeline runs at.

    python eval/extract_poses.py --mode balanced
"""
import argparse
import pickle
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from aabhas.pose import PoseEstimator  # noqa: E402

URFD = ROOT / "datasets" / "urfd"
CROP_X = 320    # the clips are depth (left) and RGB (right) side by side


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="balanced")
    ap.add_argument("--stride", type=int, default=3, help="keep every Nth frame (30 fps / 3 = 10 fps)")
    args = ap.parse_args()
    pe = PoseEstimator(args.mode)
    out_dir = URFD / f"poses_{args.mode}"
    out_dir.mkdir(exist_ok=True)
    for kind in ("falls", "adl"):
        for video in sorted((URFD / kind).glob("*.mp4")):
            dest = out_dir / f"{video.stem}.pkl"
            if dest.exists():
                continue
            cap = cv2.VideoCapture(str(video))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frames, i = [], 0
            while True:
                ok, img = cap.read()
                if not ok:
                    break
                i += 1                      # 1-based, matches the label CSV
                if (i - 1) % args.stride:
                    continue
                dets = pe(img[:, CROP_X:])
                frames.append((i, [(d.box, d.kpts, d.scores) for d in dets]))
            pickle.dump({"fps": fps, "n_frames": i, "frames": frames}, open(dest, "wb"))
            print(video.stem, i, flush=True)


if __name__ == "__main__":
    main()
