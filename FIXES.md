# FIXES: Aabhas upgrade

## How to review

Nothing is committed. All changes are in the working tree.

```
git status
git diff --stat
```

To throw everything away and go back to the original commit:

```
git restore .
git clean -fd
```

Warning: `git clean -fd` deletes every new file, including `aabhas/`, `docs/`, `eval/`, `tests/` and the `.venv` (the venv and `datasets/` are ignored, so `-fd` keeps them; add `-x` only if you want those gone too). Your old code, recordings and trained model are moved, not deleted: they are in `_old/`. `git restore .` puts the originals back in place, after which you can delete `_old/` yourself.

## What was broken (audit of the original)

- The core claim ("predict potential emergencies or specific intents") was not real. There was no measurement on real footage at all.
- Training data was partly random noise: `generate_mock_data.py` made 100 samples per class from `np.random.randn`, and those were mixed in with 15 downloaded clips. The "Collapse" class on the synthetic part was a shifted random pose. The saved model had never been scored on anything held out.
- Old detector on real fall video (measured now): 23 of 30 falls found, but 133 false events in 5 minutes of daily activity.
- One person only. MediaPipe returned a single pose, so "people count" could only be 0 or 1. The README promised tracking of "targets".
- The buffer was cleared every time the person was not detected for one frame.
- `app.py` opened the webcam at import time, kept state in globals, ran inference inside the video generator (so it ran once per connected browser and the status route changed only while someone watched), and served on `0.0.0.0` with no auth.
- `psutil` was imported but missing from `requirements.txt`.
- "Velocity (m/s)" and "accel (g)" were MediaPipe world-coordinate differences multiplied by an assumed 30 fps. They were never calibrated and not meters per second.
- Weights missing meant random weights with only a printed warning, and the UI would still show a "confidence".
- Altercation class: no good data and ethically messy (agreed with Ganesh to drop it).
- No tests. `__pycache__` was in the working tree. No alert, no location, no operator action, no escalation, nothing about whether anyone helps.
- Privacy: raw video was the only thing shown.

## What I changed

No commits were made, so there are no hashes. Grouped by area:

**New pipeline (`aabhas/`)**
- Multi-person pose with `rtmlib` (RTMPose + YOLOX, ONNX, CPU), Apache-2.0 code. See licence notes below.
- IoU + centroid tracker with stable ids. Fallen people are kept for 90 s without a detection and can be re-found.
- `fall_machine.py`: the explicit per-person state machine (UPRIGHT, FALL, DOWN, ALERT, ESCALATED, BEING_HELPED, RECOVERED, plus LYING and RESOLVED). Every threshold is in `config.py`, one set per camera, scaled by the person's body height in pixels.
- `monitor.py`: ties tracker and machines together, works out who counts as help, keeps a skeleton replay buffer.
- `store.py`, `hub.py`, `camera.py`, `server.py`, `web/`: SQLite event log, alerts, raw clips only for alerted events with retention, camera threads (file, webcam, RTSP), a Flask control room (tiles, alert queue, countdown, skeleton replay, acknowledge, dispatch, false alarm, event log), 1440 and 390 px layouts.
- `demo.py` and `config/demo.yaml`: the one-command demo.
- `aabhas/litter.py`, `scripts/litter.py`: experimental littering hotspots (Phase 2).

**Evaluation**: `scripts/get_data.py`, `eval/extract_poses.py`, `eval/score_urfd.py`, `eval/old_lstm_on_urfd.py`, `eval/learned_vs_rules.py`, `scripts/score_clips.py`, and `docs/STAGED-FALLS.md` for filming your own set.

**Removed / moved to `_old/`** (nothing deleted): the old `src/`, `app.py`, `main.py`, `templates/`, `static/`, `models/best_model.pth`, `data/` (including the synthetic samples), `downloads/` (your sample videos), the old README (`README.old.md`), and `_old/pydeps` (protobuf 4.x, only so the old MediaPipe code can still be run for the comparison).

**Docs**: new README, `docs/STAGED-FALLS.md`, `docs/PHASE3-PUBLIC-URINATION.md`, screenshots in `docs/screenshots/` (taken with Playwright and Edge from the running demo).

## Results

- Tests: `python -m pytest` gives 38 passed (23 state machine, 8 monitor with scripted multi-person scenes, 4 litter, config, store).
- UR Fall (camera 0 RGB, processed at 10 fps), balanced pose model, event level, thresholds chosen on odd sequences:

  | Split | Falls detected | Median delay | False FALL events (daily activities) |
  |---|---|---|---|
  | odd (used to choose) | 13 / 15 | 0.7 s | 2 in 2.4 min |
  | even (held out) | 9 / 15 | 0.9 s | 3 in 2.6 min |
  | all | 22 / 30 | 0.85 s | 5 in 5.0 min |

  Lightweight model, all: 17 / 30 and 2 false events. Raw JSON is in `docs/results/`.
- Old MediaPipe + BiLSTM on the same 70 sequences: 23 / 30, 133 false events in 5.0 min.
- New BiLSTM on RTMPose keypoints (trained odd, tested even, 5 seeds): 8 to 13 of 15, 3 to 15 false events in 2.1 min.
- ALERT path with the last detections repeated for 45 s (synthetic): 19 / 30. This only checks the chain.
- Control room and demo ran end to end on this machine: fall at about 3 s, DOWN at about 5 s, ALERT at about 18 s (15 s timer), ESCALATED 45 s later, raw clip opening written to the event log. No horizontal scroll at 390 px (`scrollWidth` 390).
- Speed on this CPU: balanced about 160 ms per frame, lightweight about 30 ms.

## Still not done / didn't work

- **Never measured on outdoor CCTV or any realistic camera height and distance.** The datasets are indoor and close up. Night, rain, crowds and long range are unknown.
- Only 70 sequences and 5 minutes of non-fall footage. The false-alarm rate is not known to any useful precision. I did not find a second public no-login fall dataset I could use in the time (Le2i and similar need a login or a form). I did not try the large Multiple Cameras Fall download.
- Held-out recall is 9 of 15. Pose models are bad on people lying down, and slow crouching falls look like sitting.
- The 30 s `DOWN` to `ALERT` step cannot be measured on UR Fall: the clips end right after the fall.
- Webcam and RTSP sources are written but untested (no camera here). The litter detector was only tested on synthetic frames.
- The control room has no login unless `AABHAS_TOKEN` is set, and it uses Flask's development server. Fine for a demo, not for deployment.
- Pose runs on CPU only. I did not set up ONNX Runtime GPU for Blackwell.
- The fall start used for `down_seconds` is estimated from the pose history (the last moment before the drop), so the alert time is accurate to about a second.
- No licence file in the repo.
- The skeleton of a lying person is often a tangle of lines. It shows the box and low-confidence points, but it is not a clean picture.

## Check yourself

- Run `python demo.py` and click through: acknowledge, dispatch, false alarm (try each in a separate run), the raw footage button, sound on.
- Webcam: put a `source: 0` camera in a config and fall onto a mattress (see `docs/STAGED-FALLS.md` for the safe way). I could not test any webcam.
- RTSP: try the real camera URL.
- Film the staged set and run `scripts/score_clips.py`. That is the first honest outdoor number.
- Read the wording on the alert screen. Check that "Dispatch help" and the escalation time (180 s default) match how the real control room works.
- Decide on a licence for the code, and whether to keep `_old/`.

## Decisions I made

- **Pose model:** `rtmlib` RTMPose + YOLOX over MediaPipe (single person in the old setup, and its multi-person mode needs a separate landmarker) and over Ultralytics YOLO-pose (AGPL-3.0). rtmlib and the model code are Apache-2.0. The weights were trained on public datasets with mixed terms: flagged in the README. ONNX on CPU keeps it runnable without a GPU.
- **Bounding box vs keypoints for the fall trigger:** the detector box is reliable on people lying down, and keypoints are not (scores 0.15 to 0.3). So the trigger uses the box centre and height as the main signal and the torso angle (hip to shoulder) when the keypoints are good enough. This is why it still works when the pose of a lying person is poor.
- **"Down" means "not standing", not strictly "flat".** A person who falls and then sits up on the ground, and stays, still gets an alert. The operator can mark it false. I judged a missed fall worse than an extra alert.
- **Help starts counting as soon as it arrives**, not only after `down_seconds`. If someone stops next to the person at 10 s, the alert never fires.
- **Time is video time**, so offline evaluation and the demo behave the same way as live.
- **BiLSTM dropped.** The learned trigger found more falls than the rules, but it fired several times more false events, varied a lot between seeds, and was trained on 15 falls from the same room as the test. The old one fired 133 false events in 5 minutes. I moved it to `_old/`. Altercation, and every synthetic training sample, went with it. No synthetic data appears in any reported number, except where it is labelled "synthetic" (the 45 s held-frame chain check).
- **Evaluation split:** odd and even sequence numbers (not first and second half), because the activity clips are sorted by activity and a half split would put every "lying on the floor" clip on one side. I looked at the even results once and did not tune afterwards.
- **Kept the threshold defaults** that I started with (0.3 body heights, 0.5 body heights per second). A small sweep on the odd clips (0.2 to 0.3, 0.35 to 0.5) changed the result by at most one clip either way, so I did not tune to 15 clips.
- **Demo uses the dataset's own fall clip with the last frame held**, and 15 s instead of 30 s, so the flow fits in a minute. The README says so.
- **Control room polls** `/api/state` every 0.7 s instead of using websockets. Simpler and enough.
- **Skeleton-only live tiles.** The grid never shows raw video. The raw clip is a separate button that writes an audit line.
- **Raw clip frames are JPEGs at 5 fps and 480 px wide**, played back in the page, because browsers will not play OpenCV's mp4v files.
- **Phase 2 is a deliberately small, experimental detector** (two background models plus a nearby-person check). Phase 3 is a design note only.
