"""Start the control room.   python run.py --config config/cameras.yaml"""
import argparse

from aabhas.config import load_settings
from aabhas.hub import Hub
from aabhas.server import serve


def main() -> None:
    ap = argparse.ArgumentParser(description="Aabhas control room")
    ap.add_argument("--config", default="config/cameras.yaml")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    args = ap.parse_args()
    settings = load_settings(args.config)
    host, port = args.host or settings.host, args.port or settings.port
    print(f"Control room on http://{host}:{port}")
    serve(Hub(settings), host, port)


if __name__ == "__main__":
    main()
