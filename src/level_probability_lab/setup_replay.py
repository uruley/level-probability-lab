"""Frozen-boundary setup replay. Paper testing only; a touch is not a fill."""

from __future__ import annotations

import json
import math
import webbrowser
from pathlib import Path
from typing import Any

import pandas as pd

from level_probability_lab.exceptions import LabError
from level_probability_lab.paths import ensure_dir, project_root
from level_probability_lab.storage import read_parquet
from level_probability_lab.time_model import as_utc

DEFAULT_LABELS = Path("data/labels/pilot_aug2026/labels.parquet")
DEFAULT_BARS = Path("data/labels/pilot_aug2026/normalized.parquet")
DEFAULT_OUT = Path("data/replays/setup_replay.html")


def _finite(value: Any) -> float | None:
    if value is None or value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _iso(value: Any) -> str:
    return as_utc(value).isoformat()


def _session_key(value: Any) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.strftime("%Y-%m-%d")


def build_setup_replay_payload(
    bars: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    symbol: str = "QQQ",
    session_date: str | None = None,
    k_up: float = 1.0,
    k_down: float = 1.0,
    horizon_minutes: int = 15,
) -> dict[str, Any]:
    if bars.empty:
        raise LabError("no bars to replay")
    if labels.empty:
        raise LabError("no labels to replay")

    work = bars.copy()
    if "symbol" in work.columns:
        work = work[work["symbol"] == symbol]
    if "is_regular_session" in work.columns:
        work = work[work["is_regular_session"]]
    work = work.sort_values("bar_start")
    if session_date:
        work = work[work["session_date"].map(_session_key) == session_date]
    if work.empty:
        raise LabError(f"no {symbol} regular-session bars for replay")

    lab = labels.copy()
    if "symbol" in lab.columns:
        lab = lab[lab["symbol"] == symbol]
    lab = lab.sort_values("prediction_bar_start")
    if session_date:
        lab = lab[lab["session_date"].map(_session_key) == session_date]
    if lab.empty:
        raise LabError("no labels for the requested replay window")

    sessions: list[dict[str, Any]] = []
    for date, session_bars in work.groupby(work["session_date"].map(_session_key), sort=True):
        session_labels = lab[lab["session_date"].map(_session_key) == date]
        bar_rows = []
        for rec in session_bars.itertuples(index=False):
            bar_rows.append(
                {
                    "t": _iso(rec.bar_start),
                    "o": float(rec.open),
                    "h": float(rec.high),
                    "l": float(rec.low),
                    "c": float(rec.close),
                    "v": float(rec.volume) if _finite(getattr(rec, "volume", None)) is not None else 0.0,
                    "s": str(getattr(rec, "bar_status", "observed") or "observed"),
                }
            )
        setups = []
        for rec in session_labels.itertuples(index=False):
            setups.append(
                {
                    "t": _iso(rec.prediction_bar_start),
                    "ref": _finite(rec.reference_price),
                    "up": _finite(rec.upper),
                    "lo": _finite(rec.lower),
                    "vol": _finite(rec.vol_scale),
                    "label": str(rec.label),
                    "reason": str(rec.reason),
                    "valid": bool(rec.is_valid_class),
                    "nvda": _finite(getattr(rec, "context_close", None)),
                    "tsla": _finite(getattr(rec, "context_tsla_close", None)),
                }
            )
        sessions.append({"date": date, "bars": bar_rows, "setups": setups})

    counts: dict[str, int] = {}
    for row in lab.itertuples(index=False):
        counts[str(row.label)] = counts.get(str(row.label), 0) + 1

    return {
        "symbol": symbol,
        "horizon_minutes": int(horizon_minutes),
        "k_up": float(k_up),
        "k_down": float(k_down),
        "feed": "XNAS.ITCH ohlcv-1m  ·  Nasdaq prints, not SIP  ·  a touch is not a fill",
        "counts": counts,
        "sessions": sessions,
    }


def write_setup_replay_html(path: Path, payload: dict[str, Any]) -> Path:
    ensure_dir(path.parent)
    blob = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    path.write_text(_HTML.replace("__PAYLOAD__", blob), encoding="utf-8")
    return path


def run_setup_replay(
    *,
    labels_path: Path | None = None,
    bars_path: Path | None = None,
    out_path: Path | None = None,
    session_date: str | None = None,
    open_browser: bool = False,
    root: Path | None = None,
) -> Path:
    base = root or project_root()
    labels_file = Path(labels_path) if labels_path else base / DEFAULT_LABELS
    bars_file = Path(bars_path) if bars_path else base / DEFAULT_BARS
    dest = Path(out_path) if out_path else base / DEFAULT_OUT
    if not labels_file.is_absolute():
        labels_file = base / labels_file
    if not bars_file.is_absolute():
        bars_file = base / bars_file
    if not dest.is_absolute():
        dest = base / dest
    if not labels_file.exists():
        raise LabError(f"labels parquet not found: {labels_file}")
    if not bars_file.exists():
        raise LabError(f"normalized bars parquet not found: {bars_file}")

    payload = build_setup_replay_payload(
        read_parquet(bars_file),
        read_parquet(labels_file),
        session_date=session_date,
    )
    written = write_setup_replay_html(dest, payload)
    if open_browser:
        webbrowser.open(written.resolve().as_uri())
    return written


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Level Probability Lab — setup replay</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #101214;
    --card: #171a1d;
    --ink: #e8eaed;
    --muted: #8b939c;
    --line: #2a3036;
    --up: #26a69a;
    --down: #ef5350;
    --hold: #c9a227;
    --amb: #8d6cab;
    --accent: #7eb6ff;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.4 ui-sans-serif, system-ui, sans-serif; }
  #app { max-width: 1280px; margin: 0 auto; padding: 16px 18px 28px; }
  h1 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
  .lede { color: var(--muted); font-size: 12px; margin-bottom: 14px; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 14px; align-items: start; }
  @media (max-width: 960px) { .layout { grid-template-columns: 1fr; } }
  canvas { width: 100%; height: 460px; background: var(--card); border: 1px solid var(--line); border-radius: 8px; display: block; }
  .controls { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 0; align-items: center; }
  button, select { background: var(--card); color: var(--ink); border: 1px solid var(--line); border-radius: 6px; padding: 6px 10px; cursor: pointer; font-size: 13px; }
  button:hover, select:hover { border-color: var(--accent); }
  button[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
  .legend { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .sw { display: inline-block; width: 10px; height: 10px; margin: 0 4px 0 10px; vertical-align: middle; }
  aside { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; }
  .k { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 10px 0 4px; }
  .k:first-child { margin-top: 0; }
  .big { font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .row { display: flex; justify-content: space-between; gap: 8px; font-variant-numeric: tabular-nums; margin: 3px 0; }
  .muted { color: var(--muted); }
  .stamp { margin-top: 8px; padding: 8px 10px; border-radius: 6px; border: 1px solid var(--line); font-weight: 600; }
  .stamp.upper_first { color: var(--up); border-color: var(--up); }
  .stamp.lower_first { color: var(--down); border-color: var(--down); }
  .stamp.neither { color: var(--hold); border-color: var(--hold); }
  .stamp.ambiguous { color: var(--amb); border-color: var(--amb); }
  .stamp.incomplete, .stamp.watching { color: var(--muted); }
  .bar { height: 6px; background: #22272c; border-radius: 99px; overflow: hidden; margin: 8px 0 4px; }
  .bar > span { display: block; height: 100%; background: var(--accent); width: 0; }
  .warn { font-size: 11px; color: var(--muted); margin-top: 12px; }
</style>
</head>
<body>
<div id="app">
  <h1>Level Probability Lab — frozen setup replay</h1>
  <div class="lede" id="lede"></div>
  <div class="layout">
    <div>
      <canvas id="chart" width="980" height="460"></canvas>
      <div class="controls">
        <label>Session <select id="session"></select></label>
        <label>Show <select id="filter">
          <option value="valid" selected>valid classes</option>
          <option value="upper_first">upper first</option>
          <option value="lower_first">lower first</option>
          <option value="neither">neither</option>
          <option value="ambiguous">ambiguous</option>
          <option value="incomplete">incomplete</option>
          <option value="all">all setups</option>
        </select></label>
        <button id="play">Play horizon</button>
        <button id="pause">Pause</button>
        <button id="step">Next minute</button>
        <button id="prev">Prev setup</button>
        <button id="next">Next setup</button>
        <button id="tour">Auto tour</button>
        <label>Speed
          <select id="speed">
            <option value="700">0.5x</option>
            <option value="280" selected>1x</option>
            <option value="140">2x</option>
            <option value="70">4x</option>
          </select>
        </label>
      </div>
      <div class="legend">
        <span class="sw" style="background:#26a69a"></span>actual up
        <span class="sw" style="background:#ef5350"></span>actual down
        <span class="sw" style="background:#7eb6ff"></span>frozen upper / lower
        <span class="sw" style="background:rgba(126,182,255,0.25)"></span>15-minute horizon (future hidden until play)
      </div>
    </div>
    <aside>
      <div class="k">Clock</div>
      <div id="clock" class="big">—</div>
      <div id="clockSub" class="muted"></div>
      <div class="k">Frozen setup</div>
      <div class="row"><span class="muted">QQQ close</span><span id="ref">—</span></div>
      <div class="row"><span class="muted">Upper</span><span id="up" style="color:var(--up)">—</span></div>
      <div class="row"><span class="muted">Lower</span><span id="lo" style="color:var(--down)">—</span></div>
      <div class="row"><span class="muted">Width</span><span id="width">—</span></div>
      <div class="row"><span class="muted">Vol scale</span><span id="vol">—</span></div>
      <div class="k">Horizon</div>
      <div class="bar"><span id="hfill"></span></div>
      <div id="htext" class="muted">0 / 15 minutes revealed</div>
      <div id="live" class="stamp watching">WATCHING — future hidden</div>
      <div id="stored" class="muted"></div>
      <div class="k">Context as-of</div>
      <div class="row"><span class="muted">NVDA</span><span id="nvda">—</span></div>
      <div class="row"><span class="muted">TSLA</span><span id="tsla">—</span></div>
      <div class="k">This session</div>
      <div id="sessCounts" class="muted"></div>
      <div class="warn">Paper testing only. Bounds freeze at the last completed bar and never move. Same-bar both-touches stay ambiguous. Nasdaq venue prints only.</div>
    </aside>
  </div>
</div>
<script>
const DATA = __PAYLOAD__;
const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');
let sessionIdx = 0;
let filter = 'valid';
let setupCursor = 0;
let revealed = 0;
let timer = null;
let tourWait = null;
let touring = false;

document.getElementById('lede').textContent =
  DATA.symbol + '  ·  k_up=' + DATA.k_up + ' k_down=' + DATA.k_down +
  '  ·  ' + DATA.horizon_minutes + ' elapsed minutes  ·  ' + DATA.feed;

const sessSel = document.getElementById('session');
DATA.sessions.forEach((s, i) => {
  const opt = document.createElement('option');
  opt.value = String(i);
  opt.textContent = s.date + '  (' + s.setups.filter(x => x.valid).length + ' valid)';
  sessSel.appendChild(opt);
});

function session() { return DATA.sessions[sessionIdx]; }
function setups() {
  return session().setups.filter(s => {
    if (filter === 'valid') return s.valid;
    if (filter === 'all') return true;
    return s.label === filter;
  });
}
function setup() { return setups()[setupCursor] || null; }
function freezeIdx() {
  const s = setup();
  if (!s) return 0;
  const i = session().bars.findIndex(b => b.t === s.t);
  return i < 0 ? 0 : i;
}
function fmt(n, d) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return Number(n).toFixed(d);
}
function ny(iso) {
  const dt = new Date(iso);
  return dt.toLocaleString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
}
function classifyBar(bar, up, lo) {
  if (!bar || bar.s === 'no_trade') return null;
  if (bar.s && bar.s !== 'observed') return 'incomplete';
  const hitUp = up != null && bar.h >= up;
  const hitLo = lo != null && bar.l <= lo;
  if (hitUp && hitLo) return 'ambiguous';
  if (hitUp) return 'upper_first';
  if (hitLo) return 'lower_first';
  return null;
}
function liveState() {
  const s = setup();
  if (!s) return { label: 'incomplete', reason: 'no setup', minute: 0 };
  if (s.up == null || s.lo == null) return { label: s.label, reason: s.reason, minute: 0 };
  const bars = session().bars;
  const fi = freezeIdx();
  for (let m = 1; m <= revealed; m++) {
    const bar = bars[fi + m];
    if (!bar) return { label: 'incomplete', reason: 'missing_horizon_bar', minute: m };
    const hit = classifyBar(bar, s.up, s.lo);
    if (hit) return { label: hit, reason: 'touched during replay', minute: m };
  }
  if (revealed >= DATA.horizon_minutes) return { label: 'neither', reason: 'no_boundary_touch', minute: revealed };
  return { label: 'watching', reason: 'future still hidden', minute: revealed };
}

function chartSize() {
  const dpr = window.devicePixelRatio || 1;
  const cssW = Math.max(320, canvas.clientWidth || 980);
  const cssH = 460;
  const bw = Math.round(cssW * dpr);
  const bh = Math.round(cssH * dpr);
  if (canvas.width !== bw || canvas.height !== bh) {
    canvas.width = bw;
    canvas.height = bh;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { w: cssW, h: cssH };
}

function draw() {
  const { w, h } = chartSize();
  ctx.clearRect(0, 0, w, h);
  const bars = session().bars;
  const s = setup();
  const fi = freezeIdx();
  const head = Math.min(bars.length - 1, fi + revealed);
  const first = Math.max(0, fi - 80);
  const horizonN = DATA.horizon_minutes;
  const visible = bars.slice(first, head + 1);
  const padL = 70, padR = 84, padT = 18, padB = 28;
  let lo = Infinity, hi = -Infinity;
  for (const b of visible) { lo = Math.min(lo, b.l); hi = Math.max(hi, b.h); }
  if (s && s.up != null) hi = Math.max(hi, s.up);
  if (s && s.lo != null) lo = Math.min(lo, s.lo);
  if (!isFinite(lo) || !isFinite(hi) || hi === lo) { lo = 0; hi = 1; }
  const span = hi - lo;
  lo -= span * 0.08; hi += span * 0.08;
  const slots = (fi - first + 1) + horizonN;
  const xw = (w - padL - padR) / Math.max(slots, 1);
  const y = p => padT + (1 - (p - lo) / (hi - lo)) * (h - padT - padB);
  const x = i => padL + (i + 0.5) * xw;

  const horizonStartSlot = fi - first + 1;
  ctx.fillStyle = 'rgba(126,182,255,0.08)';
  ctx.fillRect(x(horizonStartSlot) - xw * 0.5, padT, xw * horizonN, h - padT - padB);

  if (s && s.up != null && s.lo != null) {
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = '#26a69a';
    ctx.beginPath(); ctx.moveTo(padL, y(s.up)); ctx.lineTo(w - padR, y(s.up)); ctx.stroke();
    ctx.strokeStyle = '#ef5350';
    ctx.beginPath(); ctx.moveTo(padL, y(s.lo)); ctx.lineTo(w - padR, y(s.lo)); ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = '#8b939c';
    ctx.globalAlpha = 0.5;
    ctx.beginPath(); ctx.moveTo(padL, y(s.ref)); ctx.lineTo(w - padR, y(s.ref)); ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function candle(slot, b, alpha) {
    const xi = x(slot);
    const up = b.c >= b.o;
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = up ? '#26a69a' : '#ef5350';
    ctx.fillStyle = up ? '#26a69a' : '#ef5350';
    ctx.beginPath(); ctx.moveTo(xi, y(b.h)); ctx.lineTo(xi, y(b.l)); ctx.stroke();
    const top = y(Math.max(b.o, b.c)), bot = y(Math.min(b.o, b.c));
    ctx.fillRect(xi - xw * 0.3, top, xw * 0.6, Math.max(bot - top, 1));
    ctx.globalAlpha = 1;
  }
  visible.forEach((b, i) => {
    const abs = first + i;
    candle(i, b, abs === fi ? 1 : abs > fi ? 1 : 0.72);
  });
  if (s) {
    const freezeSlot = fi - first;
    ctx.strokeStyle = '#7eb6ff';
    ctx.strokeRect(x(freezeSlot) - xw * 0.45, padT, xw * 0.9, h - padT - padB);
  }

  ctx.fillStyle = '#8b939c';
  ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
  ctx.fillText(hi.toFixed(2), 8, padT + 10);
  ctx.fillText(lo.toFixed(2), 8, h - padB + 4);
  if (s && s.up != null) ctx.fillText('UP ' + s.up.toFixed(2), w - padR + 8, y(s.up) + 4);
  if (s && s.lo != null) ctx.fillText('LO ' + s.lo.toFixed(2), w - padR + 8, y(s.lo) + 4);

  const live = liveState();
  const clock = document.getElementById('clock');
  const freezeBar = bars[fi];
  clock.textContent = freezeBar ? ny(freezeBar.t) + ' ET' : '—';
  document.getElementById('clockSub').textContent = (setups().length ? (setupCursor + 1) : 0) + ' / ' + setups().length + ' setups  ·  ' + session().date;
  document.getElementById('ref').textContent = s ? fmt(s.ref, 2) : '—';
  document.getElementById('up').textContent = s ? fmt(s.up, 2) : '—';
  document.getElementById('lo').textContent = s ? fmt(s.lo, 2) : '—';
  document.getElementById('width').textContent = s && s.up != null && s.lo != null ? fmt(s.up - s.lo, 2) : '—';
  document.getElementById('vol').textContent = s ? fmt(s.vol, 4) : '—';
  document.getElementById('nvda').textContent = s ? fmt(s.nvda, 2) : '—';
  document.getElementById('tsla').textContent = s ? fmt(s.tsla, 2) : '—';
  document.getElementById('hfill').style.width = (100 * revealed / DATA.horizon_minutes) + '%';
  document.getElementById('htext').textContent = revealed + ' / ' + DATA.horizon_minutes + ' minutes revealed';
  const liveEl = document.getElementById('live');
  liveEl.className = 'stamp ' + live.label;
  const names = {upper_first:'UPPER FIRST', lower_first:'LOWER FIRST', neither:'NEITHER', ambiguous:'AMBIGUOUS', incomplete:'INCOMPLETE', watching:'WATCHING — future hidden'};
  liveEl.textContent = names[live.label] || live.label;
  document.getElementById('stored').textContent = s ? ('Stored label: ' + s.label + '  ·  ' + s.reason) : 'No setups in this filter.';
  const c = {};
  session().setups.forEach(x => { c[x.label] = (c[x.label] || 0) + 1; });
  document.getElementById('sessCounts').textContent = Object.keys(c).sort().map(k => k + ' ' + c[k]).join('  ·  ');
}

function pause() {
  if (timer) { clearInterval(timer); timer = null; }
  if (tourWait) { clearTimeout(tourWait); tourWait = null; }
  document.getElementById('play').setAttribute('aria-pressed', 'false');
  document.getElementById('tour').setAttribute('aria-pressed', touring ? 'true' : 'false');
}
function play() {
  if (timer) return;
  document.getElementById('play').setAttribute('aria-pressed', 'true');
  const tick = () => {
    const live = liveState();
    if (live.label !== 'watching') {
      if (timer) { clearInterval(timer); timer = null; }
      document.getElementById('play').setAttribute('aria-pressed', 'false');
      if (touring) {
        tourWait = setTimeout(() => { nextSetup(true); play(); }, 650);
      }
      return;
    }
    revealed = Math.min(DATA.horizon_minutes, revealed + 1);
    draw();
  };
  timer = setInterval(tick, Number(document.getElementById('speed').value));
}
function resetReveal() { pause(); revealed = 0; }
function selectSetup(i, keepTour) {
  const n = setups().length;
  if (!n) { setupCursor = 0; revealed = 0; draw(); return; }
  setupCursor = (i + n) % n;
  revealed = 0;
  if (!keepTour) touring = false;
  draw();
}
function nextSetup(keepTour) { selectSetup(setupCursor + 1, keepTour); }

sessSel.onchange = () => { sessionIdx = Number(sessSel.value); setupCursor = 0; resetReveal(); touring = false; draw(); };
document.getElementById('filter').onchange = e => { filter = e.target.value; setupCursor = 0; resetReveal(); touring = false; draw(); };
document.getElementById('play').onclick = () => { touring = false; play(); };
document.getElementById('pause').onclick = () => { touring = false; pause(); };
document.getElementById('step').onclick = () => {
  touring = false; pause();
  if (liveState().label === 'watching') revealed += 1;
  draw();
};
document.getElementById('prev').onclick = () => selectSetup(setupCursor - 1);
document.getElementById('next').onclick = () => nextSetup(false);
document.getElementById('tour').onclick = () => {
  touring = !touring;
  document.getElementById('tour').setAttribute('aria-pressed', touring ? 'true' : 'false');
  if (touring) { revealed = 0; play(); } else pause();
};
document.getElementById('speed').onchange = () => { if (timer) { const wasTour = touring; pause(); touring = wasTour; play(); } };
document.addEventListener('keydown', ev => {
  if (ev.code === 'Space') { ev.preventDefault(); if (timer) { touring = false; pause(); } else play(); }
  if (ev.key === 'n') nextSetup(false);
  if (ev.key === 'p') selectSetup(setupCursor - 1);
  if (ev.key === 'ArrowRight') { document.getElementById('step').click(); }
});
window.addEventListener('resize', draw);
draw();
</script>
</body>
</html>
"""
