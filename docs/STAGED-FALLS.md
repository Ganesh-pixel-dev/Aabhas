# Filming your own test set (staged falls)

The public data I could download is mostly indoor and close up (see the README). This protocol gets you footage that looks like your real camera, so the numbers mean something. Plan one session of about two hours with four or five friends.

## Safety first

- Nobody falls on a hard floor. Use a **mattress, gym mat or several folded duvets**, at least 2 m x 1 m, under the whole fall area. The mat will show in the footage. Accept that.
- Fall **forwards onto the hands and knees, or sideways, in slow controlled collapses**. Never backwards, never from a step, chair or kerb, never after running.
- Anyone with a bad back, wrist, knee or neck does the walking and helping roles only.
- One person who is not acting stays beside the mat as a spotter. Stop for any pain. Nobody films a take they are unsure about.
- Film on private property or with permission. Tell anyone who walks into view. Do not share the footage without every person's agreement.
- The person on the ground says "okay" aloud at the end of each take, so a real problem is never mistaken for acting.

## Camera setup

CCTV looks down at a steep angle from far away. Copy that.

- Height: **3 to 4 m** (first floor window, balcony, or a phone clamped to a pole or ladder). Keep it fixed. No handheld.
- Tilt down 20 to 35 degrees.
- 1080p, 25 or 30 fps, landscape, fixed focus and exposure, stabilisation off.
- Distance from the camera to the fall spot: film every scenario at **5 m, 10 m and 15 m**. Write down the distance. Beyond about 15 m people are too small for pose estimation, and knowing that is useful too.
- Lighting: film the same scenarios in **daylight, dusk or shade, and at night under street light**. Rain or a crowd if you can do it safely.

## Scenarios to film

Film each one **at least 3 times at each distance**, with different people and clothes (dark and light, a long coat, a backpack, a stick if someone is willing).

| Code | What happens | Aabhas should |
|---|---|---|
| `fall_no_help` | Person walks, falls on the mat, lies still. Everyone else keeps walking past without stopping. Lie for **50 s**, then get up. | FALL, then ALERT after `down_seconds` |
| `fall_help` | As above, but after 10 to 15 s one person walks over and stops next to them (kneels or stands) for at least 5 s. | FALL, then BEING_HELPED, no ALERT |
| `fall_getup` | Person falls, lies 5 to 10 s, gets up and walks on. | FALL, then RECOVERED, no ALERT |
| `lying_no_fall` | Person walks to the mat and lies down slowly (3 s or more), stays 60 s. | No FALL, no ALERT |
| `sitting` | Person sits down quickly on a chair or kerb, stays 60 s. | Nothing |
| `shoelaces` | Person bends or squats to tie shoelaces for 10 to 20 s, then walks on. | Nothing |
| `crowd_walk` | 4 to 8 people walk across and past each other for 2 minutes, some stopping to talk. | Nothing |
| `other_none` | Anything else you want to prove harmless: picking things up, running, a cyclist, crouching to a child. | Nothing |

Also film **10 minutes of ordinary, unstaged footage** in each lighting condition. This is where false alerts per hour get measured, and 10 minutes is the least that says anything.

## Naming and labelling

Name each file `<scenario>_<distance>m_<light>_<take>.mp4`, for example `fall_no_help_10m_night_02.mp4`. Put them in one folder, for example `my_clips/`.

Create `my_clips/labels.csv`:

```
file,scenario,fall_start_s
fall_no_help_10m_night_02.mp4,fall_no_help,6.4
fall_help_5m_day_01.mp4,fall_help,4.1
lying_no_fall_10m_day_01.mp4,lying_no_fall,
crowd_walk_15m_dusk_01.mp4,crowd_walk,
```

`scenario` is one of the codes above. `fall_start_s` is the second in the clip where the body starts to drop. Find it by scrubbing the clip in a video player and taking the first frame where the hips visibly move down. Leave it empty for clips with no fall. Two people should agree on these numbers.

## Scoring

```
python scripts/score_clips.py --clips my_clips --labels my_clips/labels.csv --mode balanced
```

Pass `--config config/cameras.yaml --camera cam1` to use your camera's thresholds. Keep `down_seconds` at the configured value (30 by default) and make sure the `fall_no_help` clips are long enough to reach it (50 s).

The script prints PASS or FAIL for each clip, then:

- how many clips behaved as the table says;
- the median delay from `fall_start_s` to the FALL event;
- FALL or ALERT events on the no-fall clips, per hour.

## How to read the results

- Report per distance and per light condition, not one overall number. Two or three clips per cell is thin. Say so.
- A FAIL on `fall_no_help` at 15 m at night is useful: it tells you the working range.
- Do not change thresholds, re-score the same clips and then quote the result as a test result. Split the clips: tune on takes 1 and 2, score take 3 onwards, and say which is which.
- Keep every FAIL clip. They are the best material for the next round of fixes.
