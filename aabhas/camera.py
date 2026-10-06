"""One camera: reads a video file, webcam or RTSP stream, runs pose + the monitor, keeps the latest
skeleton frame for the tiles and a short ring buffer of raw JPEGs for alerted events."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Optional

import cv2

from .config import CameraConfig
from .monitor import Event, Monitor
from .pose import PoseEstimator
from .render import draw

CLIP_FPS = 5.0
CLIP_WIDTH = 480


class CameraWorker(threading.Thread):
    def __init__(self, cfg: CameraConfig, pose: PoseEstimator, pose_lock: threading.Lock,
                 on_step: Callable[["CameraWorker", list[Event]], None],
                 process_fps: float, replay_seconds: float):
        super().__init__(daemon=True, name=f"cam-{cfg.id}")
        self.cfg = cfg
        self.pose, self.pose_lock, self.on_step = pose, pose_lock, on_step
        self.process_fps = process_fps
        self.monitor = Monitor(cfg.id, cfg.thresholds, replay_seconds)
        self.stop_flag = threading.Event()
        self.t = 0.0                       # video time, seconds
        self.size = (0, 0)
        self.status = "starting"
        self.fps = 0.0
        self.jpeg: Optional[bytes] = None
        self.raw: deque[tuple[float, bytes]] = deque()   # (t, jpeg), alerted events only ever leave memory
        self.raw_seconds = replay_seconds
        self._last_raw_t = -1e9
        self.lock = threading.Lock()

    def stop(self) -> None:
        self.stop_flag.set()

    def _open(self) -> cv2.VideoCapture:
        src = self.cfg.source
        return cv2.VideoCapture(src)

    def run(self) -> None:
        is_file = isinstance(self.cfg.source, str) and not self.cfg.source.startswith(("rtsp://", "http"))
        t_offset = 0.0
        cap = self._open()
        if not cap.isOpened():
            self.status = "no signal"
            return
        self.status = "ok"
        fps_src = cap.get(cv2.CAP_PROP_FPS) or 30.0
        wall0 = time.monotonic()
        frame_i = 0
        min_dt = 1.0 / self.process_fps
        last_proc = 0.0
        stamps: deque[float] = deque(maxlen=20)

        while not self.stop_flag.is_set():
            if is_file:
                target = (time.monotonic() - wall0) * self.cfg.speed
                grabbed, ended = False, False
                while frame_i / fps_src < target:
                    if not cap.grab():
                        ended = True
                        break
                    frame_i += 1
                    grabbed = True
                if ended:
                    if not self.cfg.loop:
                        self.status = "ended"
                        return
                    t_offset += frame_i / fps_src + 1.0
                    cap.release()
                    cap = self._open()
                    frame_i, wall0 = 0, time.monotonic()
                    self.monitor = Monitor(self.cfg.id, self.cfg.thresholds, self.raw_seconds)
                    continue
                if not grabbed:
                    time.sleep(0.005)
                    continue
                ok, frame = cap.retrieve()
                if not ok:
                    continue
                t = t_offset + frame_i / fps_src
            else:
                ok, frame = cap.read()
                if not ok:
                    self.status = "no signal"
                    time.sleep(1.0)
                    cap.release()
                    cap = self._open()
                    continue
                t = time.monotonic() - wall0
            if t - last_proc < min_dt:
                time.sleep(0.003)
                continue
            last_proc = t
            self._process(frame, t)
            stamps.append(time.monotonic())
            if len(stamps) > 2:
                self.fps = (len(stamps) - 1) / (stamps[-1] - stamps[0])
        cap.release()

    def _process(self, frame, t: float) -> None:
        x, y, w, h = self.cfg.crop or (0, 0, frame.shape[1], frame.shape[0])
        img = frame[y:y + h, x:x + w]
        with self.pose_lock:
            dets = self.pose(img)
        events = self.monitor.step(t, dets)
        skel = draw((w, h), self.monitor.people, self.cfg.name)
        ok, buf = cv2.imencode(".jpg", skel, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if t - self._last_raw_t >= 1.0 / CLIP_FPS:
            self._last_raw_t = t
            small = cv2.resize(img, (CLIP_WIDTH, int(h * CLIP_WIDTH / w)))
            okr, raw = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if okr:
                self.raw.append((t, raw.tobytes()))
                while self.raw and t - self.raw[0][0] > self.raw_seconds:
                    self.raw.popleft()
        with self.lock:
            self.t, self.size = t, (w, h)
            if ok:
                self.jpeg = buf.tobytes()
        self.on_step(self, events)
