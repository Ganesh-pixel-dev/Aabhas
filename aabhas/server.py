"""Control room web app (Flask).

By default it listens on 127.0.0.1 only. If you bind it to another address, set AABHAS_TOKEN
so that every request has to carry it (?token=... once, then a cookie).
"""
from __future__ import annotations

import hmac
import os
import time
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, send_file

from .hub import Hub

WEB = Path(__file__).resolve().parent / "web"


def create_app(hub: Hub) -> Flask:
    app = Flask(__name__, template_folder=str(WEB / "templates"), static_folder=str(WEB / "static"))
    token = os.environ.get("AABHAS_TOKEN", "")

    @app.before_request
    def check_token():
        if not token or request.path.startswith("/static/"):
            return None
        given = request.args.get("token") or request.cookies.get("aabhas_token", "")
        if not hmac.compare_digest(given, token):
            abort(401)
        return None

    @app.after_request
    def set_cookie(resp):
        if token and request.args.get("token"):
            resp.set_cookie("aabhas_token", token, httponly=True, samesite="Strict")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def state():
        return jsonify(hub.snapshot())

    @app.get("/cam/<cam_id>/stream")
    def stream(cam_id: str):
        w = hub.workers.get(cam_id)
        if w is None:
            abort(404)

        def gen():
            last = None
            while True:
                with w.lock:
                    jpg = w.jpeg
                if jpg is not None and jpg is not last:
                    last = jpg
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                time.sleep(0.08)

        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/alerts/<int:alert_id>/skeleton")
    def skeleton(alert_id: int):
        data = hub.skeleton(alert_id)
        if data is None:
            abort(404)
        return jsonify(data)

    @app.get("/api/alerts/<int:alert_id>/clip/<int:n>.jpg")
    def clip_frame(alert_id: int, n: int):
        row = hub.store.alert(alert_id)
        p = hub.store.root / "alerts" / str(alert_id) / "clip" / f"{n:05d}.jpg"
        if row is None or not p.exists():
            abort(404)
        if n == 0:
            hub.log_raw_access(alert_id)
        return send_file(p, mimetype="image/jpeg")

    @app.post("/api/alerts/<int:alert_id>/<action>")
    def operator(alert_id: int, action: str):
        if action not in ("acknowledge", "dispatch", "false_alarm"):
            abort(404)
        try:
            return jsonify(hub.operator(alert_id, action))
        except KeyError:
            abort(404)

    return app


def serve(hub: Hub, host: str, port: int) -> None:
    app = create_app(hub)
    hub.start()
    try:
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
    finally:
        hub.stop()
