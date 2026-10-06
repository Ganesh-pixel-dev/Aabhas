"""Download the UR Fall Detection dataset (camera 0 videos + frame labels).

No login needed. Licence: CC BY-NC-SA 4.0, non-commercial academic use only.
Cite: Kwolek and Kepski, Computer Methods and Programs in Biomedicine 117(3), 2014.

    python scripts/get_data.py            # about 80 MB into datasets/urfd/
"""
import argparse
import urllib.request
from pathlib import Path

BASE = "http://fenix.ur.edu.pl/mkepski/ds/data"
ROOT = Path(__file__).resolve().parent.parent / "datasets" / "urfd"


def fetch(name: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("get", name)
    urllib.request.urlretrieve(f"{BASE}/{name}", dest)


def main() -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    for csv in ("urfall-cam0-falls.csv", "urfall-cam0-adls.csv"):
        fetch(csv, ROOT / csv)
    for i in range(1, 31):
        fetch(f"fall-{i:02d}-cam0.mp4", ROOT / "falls" / f"fall-{i:02d}.mp4")
    for i in range(1, 41):
        fetch(f"adl-{i:02d}-cam0.mp4", ROOT / "adl" / f"adl-{i:02d}.mp4")
    print("done:", ROOT)


if __name__ == "__main__":
    main()
