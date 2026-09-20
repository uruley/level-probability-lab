"""Local-only Kronos replay application. Run: python -m level_probability_lab.lab."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlparse
import uuid

import numpy as np
import pandas as pd

from .calendar import session_schedule
from .exceptions import SessionBoundaryError
from .ghost_candles.ohlc import representative_path, repair_ohlc
from .ghost_candles.storage import ForecastStore
from .ghost_candles.windows import completed_input_window, future_session_timestamps
from .paths import project_root
from .chart_data import prepare as prepare_chart, payload as chart_payload
from .market_context import load_history, snapshot, save_context, location_summary
from .range_metrics import forecast_range, observed_range
from .touch_experiment import setup as touch_setup, observe as touch_observe, summary as touch_summary, save_setup

BASE_REVISION = "2b554741eca47781b64468546e77fef3e85130e6"
ROOT = project_root()
WEB = Path(__file__).with_name("lab_web")


def load_day(path: Path, date: str) -> pd.DataFrame:
    day = pd.Timestamp(date)
    if day.strftime("%Y-%m-%d") != date:
        raise ValueError("Choose a date in YYYY-MM-DD format.")
    schedule = session_schedule(date, date)
    if schedule.empty:
        raise ValueError("That date is not a regular market session.")
    opening, closing = schedule.iloc[0][["market_open", "market_close"]]
    frame = pd.read_parquet(path, filters=[("symbol", "==", "QQQ"),
        ("ts_event", ">=", opening.to_pydatetime()), ("ts_event", "<", closing.to_pydatetime())])
    frame = frame.rename(columns={"ts_event": "bar_start"}).sort_values("bar_start").reset_index(drop=True)
    if frame.empty:
        raise ValueError("No local QQQ candles for this session.")
    values = frame[["open", "high", "low", "close", "volume"]]
    if not np.isfinite(values.to_numpy(dtype=float)).all() or (values <= 0).any().any():
        raise ValueError("Session contains invalid prices or volume; it cannot be replayed.")
    if frame.bar_start.duplicated().any() or (frame.high < frame[["open", "close", "low"]].max(axis=1)).any() or (frame.low > frame[["open", "close"]].min(axis=1)).any():
        raise ValueError("Session contains duplicate timestamps or invalid OHLC.")
    frame["session_close"] = closing
    frame["session_open"] = opening
    frame["bar_end"] = frame.bar_start + pd.Timedelta(minutes=1)
    return frame


def bars_payload(frame):
    return [{"t": row.bar_start.isoformat(), "o": float(row.open), "h": float(row.high),
             "l": float(row.low), "c": float(row.close), "v": int(row.volume)} for row in frame.itertuples()]


def public_forecast(row):
    paths = np.asarray(row["sampled_paths"], dtype=float)
    return {"id": row["forecast_id"], "origin": row["last_input_timestamp"],
        "targets": row["target_timestamps"], "candles": row["displayed_path"],
        "range_forecast": forecast_range(paths, float(row["input_window"][-1]["close"])),
        "median": np.median(paths[:, :, 3], axis=0).tolist(),
        "low": np.quantile(paths[:, :, 3], .1, axis=0).tolist(),
        "high": np.quantile(paths[:, :, 3], .9, axis=0).tolist(),
        "model": row["model_name"].split("/")[-1], "samples": row["sample_count"],
        "seconds": row["inference_time_s"], "repairs": row.get("invalid_ohlc_steps", 0),
        "input_package_id": row.get("input_package_id"),
        "amount_mode": row.get("amount_mode", "approximate"),
        "cached": row.get("cached", False)}


class ReplaySession:
    def __init__(self, bars, date, lookback=120, context_history=None):
        self.context_history = context_history
        self.chart_history = prepare_chart(context_history)
        self.bars, self.date, self.lookback = bars, date, lookback
        if len(bars) < lookback:
            raise ValueError("Not enough session candles for this lookback.")
        self.cursor = lookback - 1
        self.forecasts = {}
        self.lock = threading.RLock()

    def state(self):
        revealed = self.bars.iloc[:self.cursor + 1]
        actual = {r.bar_start.isoformat(): float(r.close) for r in revealed.itertuples()}
        forecasts, errors, baseline_errors = [], [], []
        for row in self.forecasts.values():
            entry = public_forecast(row)
            entry["market_context"] = row.get("market_context")
            entry["market_context_id"] = row.get("market_context_id")
            origin_close = float(row["input_window"][-1]["close"])
            entry["actual"] = [actual.get(t) for t in entry["targets"]]
            entry["outcome_status"] = ["observed" if a is not None else
                "missing" if pd.Timestamp(t) <= revealed.iloc[-1].bar_start else "pending"
                for t, a in zip(entry["targets"], entry["actual"])]
            entry["errors"] = [None if a is None else abs(p-a) for p, a in zip(entry["median"], entry["actual"])]
            entry["baseline_errors"] = [None if a is None else abs(origin_close-a) for a in entry["actual"]]
            errors.extend(e for e in entry["errors"] if e is not None)
            baseline_errors.extend(e for e in entry["baseline_errors"] if e is not None)
            entry["range_outcome"] = observed_range(entry["range_forecast"], entry["targets"], revealed)
            entry["touch_setup"] = touch_setup(row)
            entry["touch_outcomes"] = touch_observe(entry["touch_setup"], entry["targets"], revealed)
            entry["extended_touch_outcomes"] = touch_observe(entry["touch_setup"], entry["targets"], revealed, extended=True)
            forecasts.append(entry)
        can_forecast, reason = True, ""
        try:
            completed_input_window(revealed, revealed.iloc[-1].bar_start, self.lookback)
            future_session_timestamps(revealed, revealed.iloc[-1].bar_start, 5)
        except (ValueError, SessionBoundaryError) as exc:
            can_forecast, reason = False, str(exc)
        opening = self.bars.iloc[0].session_open
        closing = self.bars.iloc[0].session_close
        expected = int((closing-opening).total_seconds() / 60)
        return {"date": self.date, "bars": bars_payload(revealed), "cursor": self.cursor,
            "total": len(self.bars), "lookback": self.lookback, "forecasts": forecasts,
            "session_open": opening.isoformat(),
            "chart_history": chart_payload(self.chart_history, revealed.iloc[-1].bar_end),
            "clock": revealed.iloc[-1].bar_end.isoformat(), "done": self.cursor == len(self.bars)-1,
            "can_forecast": can_forecast, "reason": reason,
            "location_summary": location_summary(forecasts),
            "touch_summary": touch_summary(forecasts),
            "extended_touch_summary": touch_summary(forecasts, extended=True),
            "missing_minutes": expected-len(self.bars),
            "metrics": {"scored": len(errors), "mae": float(np.mean(errors)) if errors else None,
                "baseline_mae": float(np.mean(baseline_errors)) if errors else None}}

    def advance(self, count=1):
        if count not in (1, 5):
            raise ValueError("Advance by one or five observed candles.")
        self.cursor = min(len(self.bars)-1, self.cursor+count)
        return self.state()


class Lab:
    def __init__(self, source=None, output=None):
        self.source = source or ROOT / "data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet"
        self.output = output or ROOT / "data/kronos_lab"
        self.sessions = {}
        self.model = None
        self.model_key = None
        self.model_lock = threading.Lock()
        self.store_lock = threading.Lock()
        self.store = ForecastStore(self.output / "forecasts.jsonl")
        self.saved = {}
        saved_path = ROOT / "data/ghost_candles/2026-08-14/forecasts.jsonl"
        if saved_path.exists():
            for row in ForecastStore(saved_path).all():
                self.saved[row["last_input_timestamp"]] = row

    @lru_cache(maxsize=1)
    def catalog(self):
        raw = pd.read_parquet(self.source, columns=["ts_event"], filters=[("symbol", "==", "QQQ")])
        dates = sorted(raw.ts_event.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d").unique())
        schedule = session_schedule(dates[0], dates[-1])
        valid = {pd.Timestamp(d).strftime("%Y-%m-%d") for d in schedule.index}
        return {"dates": [d for d in dates if d in valid], "default_date": "2026-08-14",
            "source": self.source.name, "saved_date": "2026-08-14"}

    def create(self, date, lookback):
        if lookback not in (60, 120, 240):
            raise ValueError("Lookback must be 60, 120, or 240 candles.")
        session = ReplaySession(load_day(self.source, date), date, lookback, load_history(self.source, date))
        sid = uuid.uuid4().hex
        self.sessions[sid] = session
        return {"session_id": sid, **session.state()}

    def get_model(self, key):
        if self.model_key == key:
            return self.model
        from .ghost_candles.adapter import KronosPathForecaster
        import torch
        if self.model is not None:
            self.model = None
            self.model_key = None
            torch.cuda.empty_cache()
        kwargs = {}
        if key == "base":
            kwargs = {"model_id": "NeoQuasar/Kronos-base", "model_revision": BASE_REVISION,
                      "cache_dir": ROOT / "data/models/hub"}
        self.model = KronosPathForecaster(**kwargs)
        self.model_key = key
        return self.model

    def predict(self, session, key, samples, amount_mode="approximate"):
        if amount_mode not in ("approximate", "trades"):
            raise ValueError("Unknown dollar amount mode")
        if amount_mode == "trades" and key == "saved":
            raise ValueError("Saved demo uses approximate dollar amount")
        if key not in ("base", "small", "saved") or samples not in (10, 25, 50):
            raise ValueError("Unsupported model or sample count.")
        visible = session.bars.iloc[:session.cursor+1]
        last = visible.iloc[-1].bar_start
        window = completed_input_window(visible, last, session.lookback)
        targets = future_session_timestamps(visible, last, 5)
        if amount_mode == "trades":
            from .trade_amount import attach_amount
            window = attach_amount(window, ROOT / "data/trade_amount_v1/amounts.parquet")
        if key == "saved":
            if session.date != "2026-08-14" or session.lookback != 120:
                raise ValueError("Saved demo requires August 14, 2026 and 120 input candles.")
            row = self.saved.get(last.isoformat())
            if row is None:
                raise ValueError("No saved forecast at this minute.")
            row = {**row, "cached": True}
        else:
            # A fixed model revision, input window, sampling settings, and seed define a forecast.
            revision = BASE_REVISION if key == "base" else "901c26c1332695a2a8f243eb2f37243a37bea320"
            fid = f"lab-v1|{last.isoformat()}|{key}|{revision}|{session.lookback}|{samples}|42"
            if amount_mode == "trades":
                digest = hashlib.sha256(window.to_json(date_format="iso", double_precision=15).encode()).hexdigest()
                fid += "|trade-amount-v1|" + digest
            with self.model_lock:
                with self.store_lock:
                    try:
                        row = {**self.store.get(fid), "cached": True}
                    except KeyError:
                        row = None
                if row is None:
                    model = self.get_model(key)
                    paths, elapsed = model.forecast_paths(window, targets, sample_count=samples, seed=42)
                    paths = np.asarray(paths, dtype=float)
                    if paths.shape != (samples, 5, 4) or not np.isfinite(paths).all():
                        raise ValueError("Model returned invalid forecast values.")
                    displayed = representative_path(paths)
                    repaired = [list(repair_ohlc(*p)) for p in displayed]
                    row = {"forecast_id": fid, "last_input_timestamp": last.isoformat(),
                        "forecast_created_at": datetime.now(timezone.utc).isoformat(),
                        "target_timestamps": [t.isoformat() for t in targets],
                        "model_name": model.model_name, "model_revision": revision,
                        "sample_count": samples, "random_seed": 42, "lookback": session.lookback,
                        "source": self.source.name, "amount_mode": amount_mode, "input_window": [
                            {"bar_start": r.bar_start.isoformat(), "open": float(r.open), "high": float(r.high),
                             "low": float(r.low), "close": float(r.close), "volume": int(r.volume),
                             "amount": float(r.amount) if amount_mode == "trades" else float(r.volume) * float(r.close)} for r in window.itertuples()],
                        "sampled_paths": paths.tolist(), "displayed_path": repaired,
                        "invalid_ohlc_steps": sum(not np.array_equal(a,b) for a,b in zip(displayed,repaired)),
                        "inference_time_s": elapsed}
                    with self.store_lock:
                        self.store.put(row)
        if key != "saved":
            from .input_package import save_package
            with self.store_lock:
                package_id = save_package(row, ROOT, self.output)
            row = {**row, "input_package_id": package_id}
        frozen_setup = touch_setup(row)
        context = snapshot(session.context_history, visible, frozen_setup["risk"], frozen_setup["direction"])
        context["source"] = self.source.name
        with self.store_lock:
            context_id = save_context(context, row["forecast_id"], self.output)
            save_setup(row, self.output)
        row = {**row, "market_context": context, "market_context_id": context_id}
        session.forecasts[row["forecast_id"]] = row
        return {"forecast_id": row["forecast_id"], **session.state()}


def make_handler(lab, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, payload, status=200, content_type="application/json"):
            data = json.dumps(payload, allow_nan=False).encode() if content_type == "application/json" else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def local_request(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.local_request():
                return self.send({"error": "Local access only."}, 403)
            path = urlparse(self.path).path
            vendor_files = {"/vendor/lightweight-charts.js": "text/javascript",
                            "/vendor/LICENSE-lightweight-charts": "text/plain; charset=utf-8",
                            "/vendor/NOTICE-lightweight-charts": "text/plain; charset=utf-8"}
            if path in vendor_files:
                return self.send((WEB / "vendor" / path.rsplit("/", 1)[-1]).read_bytes(), content_type=vendor_files[path])
            if path in ("/", "/app.js", "/chart.js", "/style.css"):
                filename = {"/": "index.html", "/app.js": "app.js", "/chart.js": "chart.js", "/style.css": "style.css"}[path]
                mime = {"/": "text/html; charset=utf-8", "/app.js": "text/javascript", "/chart.js": "text/javascript", "/style.css": "text/css"}[path]
                return self.send((WEB / filename).read_bytes(), content_type=mime)
            if path == "/api/catalog":
                try:
                    return self.send({**lab.catalog(), "token": token})
                except Exception as exc:
                    return self.send({"error": str(exc)}, 400)
            self.send({"error": "Not found."}, 404)

        def do_POST(self):
            if not self.local_request() or self.headers.get("X-Lab-Token") != token:
                return self.send({"error": "Local session token required."}, 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 4096:
                    raise ValueError("Invalid request length.")
                body = json.loads(self.rfile.read(length))
                if self.path == "/api/session":
                    return self.send(lab.create(str(body["date"]), int(body.get("lookback", 120))))
                session = lab.sessions.get(body.get("session_id"))
                if session is None:
                    raise ValueError("Load a session first.")
                with session.lock:
                    if self.path == "/api/step":
                        state = session.advance(int(body.get("count", 1)))
                        from .input_package import save_outcomes
                        with lab.store_lock:
                            save_outcomes(state, lab.output)
                        return self.send(state)
                    if self.path == "/api/forecast":
                        return self.send(lab.predict(session, str(body["model"]), int(body.get("samples", 25)), str(body.get("amount_mode", "approximate"))))
                    if self.path == "/api/state":
                        return self.send(session.state())
                self.send({"error": "Not found."}, 404)
            except Exception as exc:
                self.send({"error": str(exc)}, 400)
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Local Kronos Lab")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    lab = Lab()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(lab, secrets.token_urlsafe(32)))
    print(f"Kronos Lab: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
