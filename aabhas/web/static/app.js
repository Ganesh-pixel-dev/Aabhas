"use strict";

const $ = (id) => document.getElementById(id);
const EDGES = [[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16],[0,1],[0,2],[1,3],[2,4]];
const STATE_LABEL = {
  ALERT: "ALERT", ESCALATED: "ESCALATED, NOT ACKNOWLEDGED", BEING_HELPED: "BEING HELPED", DOWN: "ON THE GROUND",
  FALL: "FALLING", RECOVERED: "GOT UP", LOST: "OUT OF VIEW", RESOLVED: "FALSE ALARM",
};
const TYPE_LABEL = { ESCALATED: "ESCALATED", BEING_HELPED: "HELPED", OPERATOR: "OPERATOR" };

let snap = null, snapAt = 0, openId = null, soundOn = false, knownAlerts = new Set(), firstLoad = true;
let audio = null;

const mmss = (s) => {
  s = Math.max(0, Math.round(s));
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
};
const clockTime = (wall) => new Date(wall * 1000).toLocaleTimeString([], { hour12: false });
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

async function poll() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    snap = await r.json();
    snapAt = performance.now();
    render();
  } catch (e) {
    $("stat-open").textContent = "No connection to the server";
  }
  setTimeout(poll, 700);
}

function live(a) { return a.live; }
function sinceNow(a) { return live(a) ? a.since_fall + (performance.now() - snapAt) / 1000 : a.since_fall; }

function render() {
  const open = snap.alerts.filter(live);
  $("stat-cams").textContent = `Cameras ${snap.cameras.filter((c) => c.status === "ok").length}/${snap.cameras.length}`;
  const so = $("stat-open");
  so.textContent = `Open alerts ${open.length}`;
  so.classList.toggle("has", open.length > 0);
  document.title = open.length ? `(${open.length}) ALERT - Aabhas` : "Aabhas control room";

  renderCams();
  renderQueue(open);
  renderWatch();
  renderLog();
  renderBanner(open);
  if (openId != null) renderDrawer();

  for (const a of open) {
    if (!knownAlerts.has(a.id) && !firstLoad) beep();
    knownAlerts.add(a.id);
  }
  firstLoad = false;
}

function renderCams() {
  const grid = $("grid");
  const watching = new Map(snap.watching.map((w) => [w.camera, w]));
  for (const c of snap.cameras) {
    let tile = document.getElementById("tile-" + c.id);
    if (!tile) {
      tile = el("figure", "tile");
      tile.id = "tile-" + c.id;
      tile.style.margin = 0;
      const img = el("img");
      img.alt = `Skeleton view of ${c.name}`;
      img.src = `/cam/${c.id}/stream`;
      const chip = el("span", "chip"); chip.dataset.k = "chip";
      const cd = el("span", "count-down"); cd.dataset.k = "cd"; cd.hidden = true;
      const bar = el("figcaption", "bar");
      const left = el("div");
      left.append(el("span", "name", c.name), document.createTextNode(" "), el("span", "where", c.location));
      const meta = el("span", "meta"); meta.dataset.k = "meta";
      bar.append(left, meta);
      tile.append(img, chip, cd, bar);
      grid.append(tile);
    }
    tile.className = `tile st-${c.state}` + (c.status === "ok" ? "" : " off");
    tile.querySelector('[data-k="chip"]').textContent = c.status === "ok" ? (STATE_LABEL[c.state] || "CLEAR") : c.status.toUpperCase();
    const w = watching.get(c.id);
    const cd = tile.querySelector('[data-k="cd"]');
    cd.hidden = !(w && w.countdown != null);
    if (!cd.hidden) cd.textContent = mmss(w.countdown);
    tile.querySelector('[data-k="meta"]').textContent = `${c.people} ${c.people === 1 ? "person" : "people"} · ${c.fps} fps`;
  }
}

function renderQueue(open) {
  const q = $("queue");
  const items = snap.alerts.filter((a) => live(a) || a.status !== "false_alarm").slice(0, 12);
  q.replaceChildren();
  for (const a of items) {
    const li = el("li");
    const b = el("button", `q s-${a.state}` + (live(a) ? "" : " done") + (a.status === "acknowledged" || a.status === "dispatched" ? " acked" : ""));
    b.type = "button";
    const r1 = el("div", "row");
    r1.append(el("span", "where", a.location), el("span", "time", mmss(sinceNow(a))));
    const r2 = el("div", "row");
    const status = live(a) ? (a.status === "open" ? "NEEDS ACTION" : a.status.toUpperCase()) : (a.status === "closed" ? "CLOSED" : "FALSE ALARM");
    r2.append(el("span", "state", `${STATE_LABEL[a.state] || a.state} · ${status}`), el("span", "sub", "since fall"));
    const r3 = el("div", "sub", `${cameraName(a.camera)} · alert ${a.id}`);
    b.append(r1, r2, r3);
    b.addEventListener("click", () => openDrawer(a.id));
    li.append(b);
    q.append(li);
  }
  $("queue-empty").hidden = items.length > 0;
  $("queue-count").textContent = open.length ? `(${open.length} open)` : "";
}

function renderWatch() {
  const ul = $("watch");
  ul.replaceChildren();
  for (const w of snap.watching) {
    const li = el("li");
    const l = el("div");
    l.append(el("strong", null, w.location), el("div", "sub", `${w.name} · person #${w.track} · ${w.state === "FALL" ? "just fell" : "still down"}`));
    l.lastChild.style.color = "var(--muted)";
    li.append(l, el("span", "t", w.countdown != null ? mmss(w.countdown) : "--:--"));
    ul.append(li);
  }
}

function renderLog() {
  const ul = $("log");
  ul.replaceChildren();
  for (const e of snap.events) {
    const li = el("li");
    li.append(el("time", null, clockTime(e.wall)));
    const d = el("div");
    d.append(el("span", `tag t-${e.type}`, TYPE_LABEL[e.type] || e.type), document.createTextNode(e.reason + " "), el("span", "where", `${cameraName(e.camera)}${e.track ? " #" + e.track : ""}`));
    li.append(d);
    ul.append(li);
  }
}

function cameraName(id) {
  const c = snap.cameras.find((c) => c.id === id);
  return c ? c.name : id;
}

function renderBanner(open) {
  const b = $("banner");
  const need = open.filter((a) => a.status === "open" && (a.state === "ALERT" || a.state === "ESCALATED"));
  b.hidden = need.length === 0;
  if (!need.length) return;
  const a = need.sort((x, y) => x.urgency - y.urgency)[0];
  b.classList.toggle("escalated", a.state === "ESCALATED");
  $("banner-title").textContent = `${a.state === "ESCALATED" ? "ESCALATED: " : ""}Person down at ${a.location}`;
  $("banner-sub").textContent = `${mmss(sinceNow(a))} since the fall. Nobody has stopped to help.` + (need.length > 1 ? ` (${need.length} alerts need action)` : "");
  $("banner-open").onclick = () => openDrawer(a.id);
}

/* ---------- alert drawer ---------- */
let skel = null, skelFor = null, frameIdx = 0, playing = true, lastTick = 0, showRaw = false, rawTimer = null;

async function openDrawer(id) {
  openId = id;
  skel = null; skelFor = null; frameIdx = 0; playing = true; showRaw = false;
  $("d-raw").hidden = true; $("d-canvas").hidden = false;
  $("d-raw-btn").textContent = "Show camera footage (opening it is logged)";
  $("d-note").textContent = "Pose lines only. No camera pixels are shown or stored with this record.";
  $("drawer").hidden = false;
  $("d-close").focus();
  renderDrawer();
  await loadSkeleton();
}

function closeDrawer() {
  openId = null;
  $("drawer").hidden = true;
  stopRaw();
}

async function loadSkeleton() {
  if (openId == null) return;
  const id = openId;
  try {
    const r = await fetch(`/api/alerts/${id}/skeleton`, { cache: "no-store" });
    if (r.ok && id === openId) {
      skel = await r.json();
      skelFor = id;
      $("d-scrub").max = Math.max(0, skel.frames.length - 1);
    }
  } catch (e) { /* the next poll tries again */ }
}

function renderDrawer() {
  const a = snap.alerts.find((x) => x.id === openId);
  if (!a) return;
  $("d-state").textContent = `${STATE_LABEL[a.state] || a.state}${live(a) ? "" : " (closed)"}`;
  $("d-title").textContent = `Person down at ${a.location}`;
  $("d-loc").textContent = `${cameraName(a.camera)} · person #${a.track} · alert ${a.id}`;
  $("d-since").textContent = mmss(sinceNow(a));
  $("d-cam").textContent = cameraName(a.camera);
  $("d-status").textContent = live(a) ? (a.status === "open" ? "Needs action" : a.status) : a.status.replace("_", " ");
  const can = live(a);
  $("a-ack").disabled = !can || a.status !== "open";
  $("a-dispatch").disabled = !can || a.status === "dispatched";
  $("a-false").disabled = !can;
  $("d-raw-btn").disabled = !a.clip_frames;
  $("d-raw-btn").hidden = !a.clip_frames;
  if (live(a) && skel && performance.now() - (renderDrawer.last || 0) > 2500) {
    renderDrawer.last = performance.now();
    loadSkeleton();
  }
}

const GROUND = new Set(["FALL", "DOWN", "ALERT", "ESCALATED", "BEING_HELPED", "RESOLVED"]);
const thr = (p) => (GROUND.has(p.state) ? 0.12 : 0.3);

function drawSkeleton(ts) {
  requestAnimationFrame(drawSkeleton);
  const canvas = $("d-canvas");
  if (openId == null || !skel || skelFor !== openId || showRaw) return;
  const frames = skel.frames;
  if (!frames.length) return;
  if (playing && ts - lastTick > 160) {
    lastTick = ts;
    frameIdx = frameIdx + 1 >= frames.length ? 0 : frameIdx + 1;
    $("d-scrub").value = frameIdx;
  } else if (!playing) {
    frameIdx = Math.min(Number($("d-scrub").value), frames.length - 1);
  }
  const f = frames[Math.min(frameIdx, frames.length - 1)];
  const [W, H] = skel.size;
  const ctx = canvas.getContext("2d");
  const s = Math.min(canvas.width / W, canvas.height / H);
  const ox = (canvas.width - W * s) / 2, oy = (canvas.height - H * s) / 2;
  ctx.fillStyle = "#0a0c0e";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (const p of f.people) {
    const subject = p.subject;
    ctx.strokeStyle = ctx.fillStyle = subject ? "#ff5a3c" : "#8d98a3";
    ctx.lineWidth = subject ? 3 : 2;
    for (const [i, j] of EDGES) {
      if (p.scores[i] < thr(p) || p.scores[j] < thr(p)) continue;
      ctx.beginPath();
      ctx.moveTo(ox + p.kpts[i][0] * s, oy + p.kpts[i][1] * s);
      ctx.lineTo(ox + p.kpts[j][0] * s, oy + p.kpts[j][1] * s);
      ctx.stroke();
    }
    for (let i = 0; i < 17; i++) {
      if (p.scores[i] < thr(p)) continue;
      ctx.beginPath();
      ctx.arc(ox + p.kpts[i][0] * s, oy + p.kpts[i][1] * s, subject ? 3.5 : 2.5, 0, 7);
      ctx.fill();
    }
  }
  const t0 = frames[0].t;
  $("d-time").textContent = `${(f.t - t0).toFixed(1)}s / ${(frames[frames.length - 1].t - t0).toFixed(1)}s`;
}

function stopRaw() { if (rawTimer) clearInterval(rawTimer); rawTimer = null; }

function toggleRaw() {
  const a = snap.alerts.find((x) => x.id === openId);
  if (!a || !a.clip_frames) return;
  showRaw = !showRaw;
  const img = $("d-raw");
  $("d-canvas").hidden = showRaw;
  img.hidden = !showRaw;
  $("d-raw-btn").textContent = showRaw ? "Back to pose lines only" : "Show camera footage (opening it is logged)";
  $("d-note").textContent = showRaw
    ? "Raw camera footage. Opening it was written to the event log. It is deleted after the retention period."
    : "Pose lines only. No camera pixels are shown or stored with this record.";
  stopRaw();
  if (showRaw) {
    let n = 0;
    const total = a.clip_frames;
    const step = () => { img.src = `/api/alerts/${a.id}/clip/${String(n).padStart(5, "0")}.jpg`; n = (n + 1) % total; };
    step();
    rawTimer = setInterval(step, 1000 / (a.clip_fps || 5));
  }
}

async function act(action) {
  if (openId == null) return;
  if (action === "false_alarm" && !confirm("Mark this as a false alarm? The raw clip will be deleted.")) return;
  await fetch(`/api/alerts/${openId}/${action}`, { method: "POST" });
  await poll.once();
}
poll.once = async () => { const r = await fetch("/api/state", { cache: "no-store" }); snap = await r.json(); snapAt = performance.now(); render(); };

function beep() {
  if (!soundOn) return;
  try {
    audio = audio || new AudioContext();
    for (let i = 0; i < 3; i++) {
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = "square"; o.frequency.value = 880;
      g.gain.value = 0.06;
      o.connect(g); g.connect(audio.destination);
      o.start(audio.currentTime + i * 0.35); o.stop(audio.currentTime + i * 0.35 + 0.2);
    }
  } catch (e) { /* no audio available */ }
}

$("sound").addEventListener("click", () => {
  soundOn = !soundOn;
  $("sound").setAttribute("aria-pressed", String(soundOn));
  $("sound").textContent = soundOn ? "Sound on" : "Sound off";
  if (soundOn) { audio = audio || new AudioContext(); audio.resume(); beep(); }
});
$("d-close").addEventListener("click", closeDrawer);
$("drawer").addEventListener("click", (e) => { if (e.target === $("drawer")) closeDrawer(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && openId != null) closeDrawer(); });
$("d-play").addEventListener("click", () => { playing = !playing; $("d-play").textContent = playing ? "Pause" : "Play"; });
$("d-scrub").addEventListener("input", () => { playing = false; $("d-play").textContent = "Play"; });
$("d-raw-btn").addEventListener("click", toggleRaw);
$("a-ack").addEventListener("click", () => act("acknowledge"));
$("a-dispatch").addEventListener("click", () => act("dispatch"));
$("a-false").addEventListener("click", () => act("false_alarm"));
setInterval(() => { $("clock").textContent = new Date().toLocaleTimeString([], { hour12: false }); }, 1000);
requestAnimationFrame(drawSkeleton);
poll();
