# Design note: public urination detection (not built)

I have not built this and I do not plan to without the conditions below. It is written down so the decision is clear.

## Why this one is different from falls

A fall alert sends help to a person who needs it. A urination alert would point at a person for doing something embarrassing and, in most places, minor. The harm from a wrong or misused alert is higher, and nobody benefits at the moment of detection.

- **Dignity.** Clips of a person urinating are intimate footage. Storing or showing them is a harm even when the detection is right.
- **Misuse.** A system that finds and keeps these clips can be used to shame, blackmail or harass a specific person, or to target groups that are already policed more.
- **False positives.** A person standing close to a wall, tying a shoe, crouching to pick something up, or leaning to be sick all look similar in a pose skeleton. Pose models are also weak on the body region that matters here. A false alert accuses a real person of something they did not do.

## What it would have to be

If it is ever built, it is counts and hotspots only:

- It records an event as place, camera, hour and a count. Nothing else.
- No video clip, still image or skeleton of the individual is stored. Faces are never kept. Processing happens in memory and the frame is dropped.
- No operator alert about a person in the moment. The output is a weekly or monthly hotspot table (for example "wall behind the market, Friday and Saturday 22:00 to 02:00") so that the owner can install a toilet, lighting or a cleaning round.
- No identification, no tracking across cameras, no link to any other record.
- Retention of the counts is set in config and short.

## What is needed before building it

1. A written purpose from whoever runs the cameras, and a statement that hotspots will be answered with infrastructure, not fines against individuals.
2. A legal check for the place it would run (data protection rules for CCTV analytics differ by country and state).
3. Real labelled footage from the actual site, with a lawful basis, to measure the false positive rate. Without that number there is no honest claim to make. I have none.
4. An independent review of the false positive cases, and a rule that a low-confidence detection is dropped, not counted.
5. A rule for small counts: hotspot cells with very few events are suppressed so that a single person cannot be inferred.

If any of these cannot be met, the right answer is not to build it.
