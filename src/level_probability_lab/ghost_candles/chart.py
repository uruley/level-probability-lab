from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from level_probability_lab.paths import ensure_dir
from level_probability_lab.time_model import as_utc


def _bar_payload(bars: pd.DataFrame) -> list[dict]:
    rows = []
    for rec in bars.sort_values("bar_start").itertuples(index=False):
        rows.append(
            {
                "t": as_utc(rec.bar_start).isoformat(),
                "o": float(rec.open),
                "h": float(rec.high),
                "l": float(rec.low),
                "c": float(rec.close),
                "v": float(rec.volume),
            }
        )
    return rows


def _forecast_payload(forecasts: list[dict]) -> list[dict]:
    out = []
    for row in forecasts:
        out.append(
            {
                "id": row["forecast_id"],
                "last": row["last_input_timestamp"],
                "targets": row["target_timestamps"],
                "ghost": row["displayed_path"],
                "bandLow": row.get("band_low") or [],
                "bandHigh": row.get("band_high") or [],
                "inference_s": row.get("inference_time_s"),
            }
        )
    return out


def write_replay_html(
    path: Path,
    *,
    bars: pd.DataFrame,
    forecasts: list[dict] | None = None,
    session_date: str,
    symbol: str,
    meta: dict | None = None,
    engines: dict[str, list[dict]] | None = None,
) -> Path:
    ensure_dir(path.parent)
    if engines is None:
        engines = {"kronos-small": forecasts or []}
    payload = {
        "symbol": symbol,
        "session_date": session_date,
        "bars": _bar_payload(bars),
        "engines": {name: _forecast_payload(rows) for name, rows in engines.items()},
        "forecasts": _forecast_payload(next(iter(engines.values())) if engines else []),
        "meta": meta or {},
        "notes": {
            "displayed_path": "sampled path nearest the median close vector (not an OHLC average)",
            "band": "10th percentile of sampled lows / 90th percentile of sampled highs",
        },
    }
    html = _HTML.replace("__PAYLOAD__", json.dumps(payload))
    path.write_text(html, encoding="utf-8")
    return path


def write_freeze_png(
    path: Path,
    *,
    bars: pd.DataFrame,
    forecast: dict,
    history: int = 40,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    ensure_dir(path.parent)
    last = as_utc(forecast["last_input_timestamp"])
    work = bars.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    hist = work.loc[work["bar_start"] <= last].tail(history)
    fig, ax = plt.subplots(figsize=(12, 6), dpi=140)
    fig.patch.set_facecolor("#111111")
    ax.set_facecolor("#111111")

    def _candle(ax_, i, o, h, l, c, edge, fill, width=0.6, alpha=1.0):
        color = "#26a69a" if c >= o else "#ef5350"
        ax_.vlines(i, l, h, color=edge, linewidth=1, alpha=alpha)
        bottom = min(o, c)
        height = max(abs(c - o), 1e-6)
        ax_.add_patch(
            Rectangle((i - width / 2, bottom), width, height, facecolor=fill or color, edgecolor=edge, alpha=alpha, linewidth=0.8)
        )

    xs = list(range(len(hist)))
    for i, rec in enumerate(hist.itertuples(index=False)):
        _candle(ax, i, float(rec.open), float(rec.high), float(rec.low), float(rec.close), "#cccccc", None)
    ghost = forecast["displayed_path"]
    g0 = len(hist)
    lows = forecast.get("band_low") or []
    highs = forecast.get("band_high") or []
    if lows and highs:
        gx = [g0 + i for i in range(len(ghost))]
        ax.fill_between(gx, lows, highs, color="#42a5f5", alpha=0.18, linewidth=0)
    for i, candle in enumerate(ghost):
        o, h, l, c = (float(x) for x in candle[:4])
        _candle(ax, g0 + i, o, h, l, c, "#90caf9", "#42a5f5", alpha=0.45)
    ax.set_title(
        f"QQQ ghost candles @ {last.isoformat()}  (translucent = Kronos-small representative path)",
        color="#eeeeee",
        fontsize=11,
    )
    ax.tick_params(colors="#bbbbbb")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.set_xlim(-1, g0 + len(ghost) + 0.5)
    ax.set_ylabel("Price", color="#bbbbbb")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>QQQ ghost-candle replay</title>
<style>
  :root { color-scheme: dark; }
  html, body { margin: 0; padding: 0; background: transparent; color: var(--foreground, #e8e8e8); font-family: var(--font-sans, ui-sans-serif, system-ui, sans-serif); }
  #wrap { max-width: 1100px; }
  h1 { font-size: 16px; font-weight: 600; margin: 8px 0 4px; }
  .sub { color: var(--muted-foreground, #9aa0a6); font-size: 12px; margin-bottom: 8px; }
  canvas { width: 100%; height: 420px; border: 1px solid var(--border, #333); border-radius: 8px; background: var(--card, #141414); display: block; }
  .controls { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; align-items: center; }
  button, select { background: var(--card, #1e1e1e); color: var(--foreground, #eee); border: 1px solid var(--border, #444); border-radius: 6px; padding: 6px 10px; cursor: pointer; font-size: 13px; }
  button:hover { border-color: var(--accent, #42a5f5); }
  #status { font-size: 12px; color: var(--muted-foreground, #9aa0a6); }
  .legend { font-size: 12px; color: var(--muted-foreground, #9aa0a6); margin-top: 6px; }
  .sw { display: inline-block; width: 10px; height: 10px; margin: 0 4px 0 10px; vertical-align: middle; }
</style>
</head>
<body>
<div id="wrap">
  <h1>QQQ five-minute ghost-candle replay</h1>
  <div class="sub" id="subtitle"></div>
  <canvas id="chart" width="1100" height="420"></canvas>
  <div class="controls">
    <button id="play">Play</button>
    <button id="pause">Pause</button>
    <button id="nextMin">Next minute</button>
    <button id="prevFc">Previous forecast</button>
    <button id="nextFc">Next forecast</button>
    <label>Engine
      <select id="engine"></select>
    </label>
    <label>Speed
      <select id="speed">
        <option value="800">0.5x</option>
        <option value="400" selected>1x</option>
        <option value="200">2x</option>
        <option value="100">4x</option>
        <option value="50">8x</option>
      </select>
    </label>
    <span id="status"></span>
  </div>
  <div class="legend">
    <span class="sw" style="background:#26a69a"></span>actual up
    <span class="sw" style="background:#ef5350"></span>actual down
    <span class="sw" style="background:rgba(66,165,245,0.45)"></span>Kronos ghost (representative sampled path)
    <span class="sw" style="background:rgba(66,165,245,0.2)"></span>10–90% sampled envelope
  </div>
</div>
<script>
const DATA = __PAYLOAD__;
const bars = DATA.bars;
const ENGINES = DATA.engines || { 'kronos-small': DATA.forecasts || [] };
let engine = Object.keys(ENGINES)[0];
let forecasts = ENGINES[engine] || [];
let byLast = {};
let fcIndexes = [];
const lastIndex = Object.fromEntries(bars.map((b,i) => [b.t, i]));
let idx = Math.min(120, bars.length - 6);
let timer = null;
const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');
function setEngine(name) {
  engine = name;
  forecasts = ENGINES[engine] || [];
  byLast = Object.fromEntries(forecasts.map(f => [f.last, f]));
  fcIndexes = forecasts.map(f => lastIndex[f.last]).filter(i => i !== undefined);
  document.getElementById('subtitle').textContent =
    DATA.symbol + '  ' + DATA.session_date + '  ·  engine ' + engine +
    '  ·  displayed path = sample nearest median close, not an OHLC average';
}
const engSel = document.getElementById('engine');
Object.keys(ENGINES).forEach(name => {
  const opt = document.createElement('option');
  opt.value = name; opt.textContent = name;
  engSel.appendChild(opt);
});
engSel.onchange = () => { setEngine(engSel.value); draw(); };
setEngine(engine);

function color(css, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(css).trim();
  return v || fallback;
}

function draw() {
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0,0,w,h);
  const visible = bars.slice(Math.max(0, idx - 79), idx + 1);
  const fc = byLast[bars[idx].t];
  const ghosts = fc ? fc.ghost : [];
  const padL = 56, padR = 16, padT = 16, padB = 28;
  let lo = Infinity, hi = -Infinity;
  for (const b of visible) { lo = Math.min(lo, b.l); hi = Math.max(hi, b.h); }
  ghosts.forEach((g,i) => {
    lo = Math.min(lo, g[2], fc.bandLow[i] ?? g[2]);
    hi = Math.max(hi, g[1], fc.bandHigh[i] ?? g[1]);
  });
  const span = (hi - lo) || 1;
  lo -= span * 0.08; hi += span * 0.08;
  const n = visible.length + (ghosts.length ? ghosts.length : 0);
  const xw = (w - padL - padR) / Math.max(n, 1);
  const y = p => padT + (1 - (p - lo) / (hi - lo)) * (h - padT - padB);
  const x = i => padL + (i + 0.5) * xw;

  if (fc && fc.bandLow.length) {
    ctx.beginPath();
    ghosts.forEach((_, i) => {
      const xi = x(visible.length + i);
      if (i === 0) ctx.moveTo(xi, y(fc.bandHigh[i]));
      else ctx.lineTo(xi, y(fc.bandHigh[i]));
    });
    for (let i = ghosts.length - 1; i >= 0; i--) ctx.lineTo(x(visible.length + i), y(fc.bandLow[i]));
    ctx.closePath();
    ctx.fillStyle = 'rgba(66,165,245,0.16)';
    ctx.fill();
  }

  function candle(i, o, hgt, l, c, stroke, fill, alpha) {
    const xi = x(i);
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = stroke;
    ctx.beginPath();
    ctx.moveTo(xi, y(hgt));
    ctx.lineTo(xi, y(l));
    ctx.stroke();
    const top = y(Math.max(o,c)), bot = y(Math.min(o,c));
    ctx.fillStyle = fill;
    ctx.fillRect(xi - xw * 0.3, top, xw * 0.6, Math.max(bot - top, 1));
    ctx.strokeRect(xi - xw * 0.3, top, xw * 0.6, Math.max(bot - top, 1));
    ctx.globalAlpha = 1;
  }

  visible.forEach((b, i) => {
    const up = b.c >= b.o;
    candle(i, b.o, b.h, b.l, b.c, up ? '#26a69a' : '#ef5350', up ? '#26a69a' : '#ef5350', 1);
  });
  ghosts.forEach((g, i) => {
    candle(visible.length + i, g[0], g[1], g[2], g[3], '#90caf9', 'rgba(66,165,245,0.45)', 0.9);
  });

  ctx.fillStyle = color('--muted-foreground', '#9aa0a6');
  ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
  ctx.fillText(hi.toFixed(2), 6, padT + 8);
  ctx.fillText(lo.toFixed(2), 6, h - padB);
  const st = document.getElementById('status');
  const t = bars[idx].t.replace('T', ' ').replace('+00:00', 'Z');
  st.textContent = t + '  bar ' + (idx+1) + '/' + bars.length + (fc ? '  ·  forecast ' + fc.id.split('|')[1] : '  ·  no forecast');
}

function setIdx(v) {
  idx = Math.max(0, Math.min(bars.length - 1, v));
  draw();
}
function play() {
  if (timer) return;
  const ms = Number(document.getElementById('speed').value);
  timer = setInterval(() => {
    if (idx >= bars.length - 1) { pause(); return; }
    setIdx(idx + 1);
  }, ms);
}
function pause() { if (timer) { clearInterval(timer); timer = null; } }
document.getElementById('play').onclick = play;
document.getElementById('pause').onclick = pause;
document.getElementById('nextMin').onclick = () => { pause(); setIdx(idx+1); };
document.getElementById('prevFc').onclick = () => {
  pause();
  const prev = fcIndexes.filter(i => i < idx).pop();
  if (prev !== undefined) setIdx(prev);
};
document.getElementById('nextFc').onclick = () => {
  pause();
  const nxt = fcIndexes.find(i => i > idx);
  if (nxt !== undefined) setIdx(nxt);
};
document.getElementById('speed').onchange = () => { if (timer) { pause(); play(); } };
setIdx(idx);
</script>
</body>
</html>
"""
