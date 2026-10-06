"""One command, one minute: a person falls on camera 1 and nobody helps.

    python demo.py

It downloads a few UR Fall clips (non-commercial research data, about 6 MB), builds a demo video
by holding the last frame of one fall clip so the person stays on the ground, and starts the
control room with short timers (alert after 15 s on the ground, escalation after 45 s). The held
frame is a stand-in for a person who does not move; it is not real footage of that.
"""
import argparse
import shutil
import sys
import threading
import webbrowser
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aabhas.config import load_settings  # noqa: E402
from aabhas.hub import Hub  # noqa: E402
from aabhas.server import serve  # noqa: E402
import get_data  # noqa: E402

DEMO_DIR = ROOT / "runtime" / "demo"
HOLD_S = 90


def build_fall_video(src: Path, dest: Path) -> None:
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    out = cv2.VideoWriter(str(dest), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 480))
    last = None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        last = cv2.resize(f[:, 320:], (640, 480))
        out.write(last)
    for _ in range(int(HOLD_S * fps)):
        out.write(last)
    out.release()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("fall-01-cam0.mp4", "adl-03-cam0.mp4", "adl-08-cam0.mp4", "adl-12-cam0.mp4"):
        sub = "falls" if name.startswith("fall") else "adl"
        get_data.fetch(name, get_data.ROOT / sub / name.replace("-cam0", ""))
    video = DEMO_DIR / "fall.mp4"
    if not video.exists():
        build_fall_video(get_data.ROOT / "falls" / "fall-01.mp4", video)

    settings = load_settings(ROOT / "config" / "demo.yaml")
    shutil.rmtree(settings.data_dir, ignore_errors=True)   # the demo always starts with an empty log
    url = f"http://127.0.0.1:{args.port}"
    print(f"Demo control room: {url}")
    print("Camera 1 plays a fall at about 3 s. An alert appears after 15 s on the ground.")
    if not args.no_browser:
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    serve(Hub(settings), "127.0.0.1", args.port)


if __name__ == "__main__":
    main()
