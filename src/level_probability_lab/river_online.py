"""Independent, event-sourced River reliability experiment. No feed/model APIs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

VERSION = "river-logistic-v1"
SCHEMA = "river-features-v1"
RIVER_VERSION = "0.22.0"


def stamp(value):
    value = pd.Timestamp(value)
    if value.tzinfo is None:
        raise ValueError("Timezone-aware timestamps required")
    return value.tz_convert("UTC")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


@contextmanager
def single_writer(folder):
    """OS lock is released even if the worker crashes; stale files are harmless."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "writer.lock").open("a+b") as handle:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            if handle.read(1) == b"":
                handle.write(b"0"); handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def packets(row):
    """Allowlist frozen fields; never read outcome snapshots or current history."""
    history = row["input_window"]
    times = [stamp(b["bar_start"]) for b in history]
    origin = stamp(row["last_input_timestamp"]) + pd.Timedelta(minutes=1)
    if len(times) < 6 or times != sorted(set(times)) or times[-1] + pd.Timedelta(minutes=1) != origin:
        raise ValueError("Invalid input cutoff/order or insufficient history")
    # Short-window features must cover elapsed minutes, never bridge missing bars.
    if times[-6:] != list(pd.date_range(origin-pd.Timedelta(minutes=6), periods=6, freq="min")):
        raise ValueError("Missing recent input minutes")
    values = np.asarray([[b[k] for k in ("open", "high", "low", "close", "volume")] for b in history], float)
    if (not np.isfinite(values).all() or (values[:, :4] <= 0).any() or
            (values[:, 4] < 0).any() or (values[:, 1] < values[:, [0, 2, 3]].max(axis=1)).any() or
            (values[:, 2] > values[:, [0, 3]].min(axis=1)).any()):
        raise ValueError("Invalid frozen OHLCV")
    targets = [stamp(t) for t in row["target_timestamps"]]
    if targets != list(pd.date_range(origin, periods=5, freq="min")):
        raise ValueError("Only five elapsed one-minute horizons are supported")
    paths = np.asarray(row["sampled_paths"], float)
    if paths.ndim != 3 or paths.shape[1:] != (5, 4) or not len(paths) or not np.isfinite(paths).all():
        raise ValueError("Invalid Kronos paths")
    reference = float(values[-1, 3])
    close = np.median(paths[:, :, 3], axis=0)
    if (close <= 0).any():
        raise ValueError("Invalid predicted close")
    policy = row.get("session_policy", "rth")
    ny = origin.tz_convert("America/New_York")
    recent = values[-6:]
    returns = np.diff(recent[:, 3]) / recent[:-1, 3]
    x = dict(current_close=reference, current_open=float(values[-1, 0]),
             current_high=float(values[-1, 1]), current_low=float(values[-1, 2]),
             current_volume=float(values[-1, 4]), return_1=float(returns[-1]),
             return_5=float(reference/recent[0, 3]-1), volatility_5=float(np.std(returns)),
             range_5=float(np.mean(recent[-5:, 1]-recent[-5:, 2])/reference),
             minutes_since_open=float(ny.hour*60+ny.minute-(240 if policy == "pre-rth-v1" else 570)))
    volume_mean = float(recent[-5:, 4].mean())
    x["relative_volume_5"] = float(values[-1, 4]/volume_mean) if volume_mean else 0.0
    x["relative_volume_missing"] = float(volume_mean == 0)
    context = row.get("forward_context") or {}
    if context and stamp(context["as_of"]) > origin:
        raise ValueError("Future context cutoff")
    for field in ("session_vwap_approx", "sma200"):
        value = context.get(field)
        valid = value is not None and math.isfinite(float(value)) and float(value) > 0
        x[field+"_distance"] = reference/float(value)-1 if valid else 0.0
        x[field+"_missing"] = float(not valid)
    symbol = row.get("symbol", "QQQ")
    for h, predicted in enumerate(close, 1):
        features = dict(x, predicted_move=float(predicted/reference-1),
                        predicted_magnitude=float(abs(predicted/reference-1)),
                        predicted_direction=float(np.sign(predicted-reference)))
        # Invalid raw OHLC paths do not become valid ranges by display repair.
        p = paths[:, :h]
        valid = ((p > 0).all(axis=(1, 2)) &
                 (p[:, :, 1] >= p[:, :, [0, 2, 3]].max(axis=2)).all(axis=1) &
                 (p[:, :, 2] <= p[:, :, [0, 3]].min(axis=2)).all(axis=1))
        features["predicted_range"] = float(np.median(p[valid, :, 1].max(axis=1)-p[valid, :, 2].min(axis=1))/reference) if valid.any() else 0.0
        features["predicted_range_missing"] = float(not valid.any())
        key = json.dumps([symbol, policy, row["model_name"], row.get("model_revision", "unknown"), h], separators=(",", ":"))
        yield dict(id=hashlib.sha256(f'{row["forecast_id"]}|{h}'.encode()).hexdigest(),
                   forecast_id=row["forecast_id"], symbol=symbol, horizon=h, origin=origin.isoformat(),
                   target=targets[h-1].isoformat(), due=(targets[h-1]+pd.Timedelta(minutes=1)).isoformat(),
                   reference=reference, predicted_close=float(predicted), direction=int(np.sign(predicted-reference)),
                   features=features, model_key=key, model_version=VERSION, feature_schema=SCHEMA,
                   kronos_model=row["model_name"], kronos_revision=row.get("model_revision", "unknown"),
                   session_policy=policy, forecast_created_at=row.get("forecast_created_at"))


class OnlineModel:
    """Explicit River preprocessing: prediction never updates scaler statistics."""
    def __init__(self):
        import river
        from river import linear_model, optim, preprocessing
        if river.__version__ != RIVER_VERSION:
            raise ValueError("Install the pinned River 0.22.0 extra")
        self.scaler = preprocessing.StandardScaler()
        self.classifier = linear_model.LogisticRegression(optimizer=optim.SGD(0.01), l2=0.001)
        self.count = 0
        self.correct = 0
        self.recent = deque(maxlen=100)

    def predict(self, x):
        x = dict(sorted(x.items()))
        return float(self.classifier.predict_proba_one(self.scaler.transform_one(x)).get(True, 0.5))

    def learn(self, x, label):
        x = dict(sorted(x.items()))
        self.scaler.learn_one(x)
        self.classifier.learn_one(self.scaler.transform_one(x), bool(label))
        self.count += 1
        self.correct += label
        self.recent.append(label)


def loss(probability, label):
    p = min(1-1e-15, max(1e-15, probability))
    return dict(brier=(probability-label)**2, log_loss=-(label*math.log(p)+(1-label)*math.log1p(-p)))


def outcome(packet, bars, now):
    """Resolve a horizon only after every elapsed target minute has completed."""
    if stamp(now) < stamp(packet["due"]):
        return None
    expected = pd.date_range(stamp(packet["origin"]), periods=packet["horizon"], freq="min")
    by_time = defaultdict(list)
    for b in bars:
        t = stamp(b["bar_start"])
        if t in expected and stamp(b.get("bar_end", t+pd.Timedelta(minutes=1))) <= stamp(now):
            by_time[t].append(b)
    result = dict(quality="incomplete", label=None, actual_close=None, actual_direction=None)
    if any(len(by_time[t]) != 1 for t in expected):
        return result
    for t in expected:
        b = by_time[t][0]
        v = [float(b[k]) for k in ("open", "high", "low", "close")]
        if not all(math.isfinite(n) and n > 0 for n in v) or v[1] < max(v) or v[2] > min(v):
            return result
        if stamp(b.get("bar_end", t+pd.Timedelta(minutes=1))) != t+pd.Timedelta(minutes=1):
            return result
    actual = float(by_time[expected[-1]][0]["close"])
    direction = int(np.sign(actual-packet["reference"]))
    quality = "neutral_forecast" if packet["direction"] == 0 else "neutral_actual" if direction == 0 else "complete"
    return dict(quality=quality, label=int(direction == packet["direction"]) if quality == "complete" else None,
                actual_close=actual, actual_direction=direction, actual_move=actual-packet["reference"],
                absolute_error=abs(actual-packet["predicted_close"]),
                relative_error=abs(actual-packet["predicted_close"])/packet["reference"])


class Engine:
    """One writer. Atomic immutable JSON events are the authoritative checkpoint.

    Reconstructing from scored outcomes avoids unsafe pickle and the two-file
    checkpoint/update crash window. Never call predict again during recovery.
    """
    def __init__(self, folder, mode):
        self.folder = Path(folder)
        self.mode = mode
        self.models = defaultdict(OnlineModel)
        self.predictions = {}
        self.outcomes = {}
        self.rejections = {}
        self.seq = 0
        self.last_time = None
        self.failed = False
        (self.folder / "events").mkdir(parents=True, exist_ok=True)
        for path in sorted((self.folder / "events").glob("*.json")):
            event = json.loads(path.read_text(encoding="utf-8"))
            if event["seq"] != self.seq+1 or event["mode"] != mode or event["version"] != VERSION or event["river_version"] != RIVER_VERSION:
                raise ValueError("Incompatible/noncontiguous River journal")
            if self.last_time is not None and stamp(event["time"]) < self.last_time:
                raise ValueError("Nonchronological River journal")
            self._apply(event)

    def _apply(self, event):
        data = event["data"]
        if event["kind"] == "prediction":
            if data["id"] in self.predictions:
                raise ValueError("Duplicate prediction event")
            self.predictions[data["id"]] = data
        elif event["kind"] == "outcome":
            if data["id"] in self.outcomes:
                raise ValueError("Duplicate outcome event")
            self.outcomes[data["id"]] = data
            p = self.predictions[data["id"]]
            if data["updated"]:
                self.models[p["model_key"]].learn(p["features"], data["label"])
        elif event["kind"] == "rejection":
            self.rejections[data["forecast_id"]] = data
        else:
            raise ValueError("Unknown River event")
        self.seq = event["seq"]
        self.last_time = stamp(event["time"])

    def _commit(self, kind, data, now):
        now = stamp(now)
        if self.failed or (self.last_time is not None and now < self.last_time):
            raise ValueError("Restart failed engine / reject out-of-order event")
        event = dict(seq=self.seq+1, time=now.isoformat(), mode=self.mode, version=VERSION,
                     river_version=RIVER_VERSION, kind=kind, data=data)
        path = self.folder / "events" / f'{event["seq"]:012d}.json'
        if path.exists():
            raise ValueError("Event exists; restart required")
        # Save score and update intent BEFORE learn_one. Recovery applies it once.
        try:
            atomic_json(path, event)
            self._apply(event)
        except Exception:
            self.failed = True
            raise

    def predict(self, packet, now):
        if packet["id"] in self.predictions:
            return self.predictions[packet["id"]]
        now = stamp(now)
        if now < stamp(packet["origin"]):
            raise ValueError("Forecast not yet available")
        model = self.models[packet["model_key"]]
        quality = "eligible"
        if self.mode == "live":
            created = packet["forecast_created_at"]
            if not created or stamp(created) > now or now >= stamp(packet["origin"])+pd.Timedelta(minutes=1):
                quality = "late_or_unknown"
        data = dict(packet, predicted_at=now.isoformat(), eligibility=quality,
                    probability=model.predict(packet["features"]) if quality == "eligible" else None,
                    historical_probability=model.correct/model.count if model.count else 0.5,
                    rolling_probability=sum(model.recent)/len(model.recent) if model.recent else 0.5,
                    prior_observations=model.count)
        self._commit("prediction", data, now)
        return data

    def resolve(self, identity, bars, now):
        if identity in self.outcomes:
            return self.outcomes[identity]
        p = self.predictions[identity]
        result = outcome(p, bars, now)
        if result is None:
            return None
        if p["eligibility"] != "eligible":
            result.update(quality=p["eligibility"], label=None)
        updated = result["label"] is not None
        result.update(id=identity, resolved_at=stamp(now).isoformat(), probability=p["probability"], updated=updated)
        if updated:
            result.update(loss(p["probability"], result["label"]))
            result["baseline_losses"] = {name: loss(p[name+"_probability"], result["label"]) for name in ("historical", "rolling")}
        self._commit("outcome", result, now)
        return result

    def report(self):
        groups = defaultdict(list)
        for p in self.predictions.values():
            groups[p["model_key"]].append(p)
        reports = []
        for key, predictions in sorted(groups.items()):
            scored = [(p, self.outcomes[p["id"]]) for p in predictions if p["id"] in self.outcomes and self.outcomes[p["id"]]["updated"]]
            n = len(scored)
            avg = lambda xs: sum(xs)/len(xs) if xs else None
            buckets = []
            for i in range(10):
                items = [(p, o) for p, o in scored if min(9, int(p["probability"]*10)) == i]
                if items:
                    buckets.append(dict(lower=i/10, upper=(i+1)/10, n=len(items),
                                        confidence=avg([p["probability"] for p, o in items]),
                                        accuracy=avg([o["label"] for p, o in items]), enough_observations=len(items)>=20))
            reports.append(dict(model_key=key, symbol=predictions[0]["symbol"], horizon=predictions[0]["horizon"],
                predictions=len(predictions), observations=n,
                accuracy=avg([int((p["probability"]>=0.5) == bool(o["label"])) for p, o in scored]),
                kronos_accuracy=avg([o["label"] for p, o in scored]),
                recent_kronos_accuracy=avg(list(self.models[key].recent)),
                mean_confidence=avg([p["probability"] for p, o in scored]),
                brier=avg([o["brier"] for p, o in scored]), log_loss=avg([o["log_loss"] for p, o in scored]),
                baselines={name: {metric: avg([o["baseline_losses"][name][metric] for p, o in scored]) for metric in ("brier", "log_loss")} for name in ("historical", "rolling")},
                calibration=buckets, calibration_status="descriptive only" if n >= 100 else "insufficient observations"))
        return dict(version=VERSION, feature_schema=SCHEMA, river_version=RIVER_VERSION, mode=self.mode,
                    events=self.seq, predictions=len(self.predictions), observations=sum(o["updated"] for o in self.outcomes.values()),
                    pending=len(self.predictions)-len(self.outcomes), quality_counts=dict(Counter(o["quality"] for o in self.outcomes.values())),
                    rejected=list(self.rejections.values()),
                    groups=reports, last_event=self.last_time.isoformat() if self.last_time is not None else None)


def read_forecasts(path):
    """Ignore an in-progress final append; malformed completed lines fail visibly."""
    if not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.endswith("\n") and line.strip()]


class ForecastTail:
    """Incremental reader of the existing append-only Kronos queue."""
    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.deferred = []

    def read(self):
        if not self.path.exists():
            return []
        if self.path.stat().st_size < self.offset:
            raise ValueError("Kronos forecast store was truncated")
        rows, self.deferred = self.deferred, []
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            while line := handle.readline():
                if not line.endswith(b"\n"):
                    break
                if line.strip():
                    rows.append(json.loads(line))
                self.offset = handle.tell()
        return rows


def recorded_bars(output, symbol, date):
    folder = Path(output)/"webull"
    if symbol != "QQQ":
        folder /= symbol
    path = folder / (date+".json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def packet_date(packet):
    return stamp(packet["origin"]).tz_convert("America/New_York").strftime("%Y-%m-%d")


def replay(rows, bar_loader, folder):
    """Counterfactual origin-time replay; recorded candle revisions are explicit."""
    folder = Path(folder)
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("Replay requires a fresh output directory; prior results are immutable")
    with single_writer(folder):
        engine = Engine(folder, "replay")
        events, skipped, identities = [], [], set()
        for row in rows:
            if row["forecast_id"] in identities:
                raise ValueError("Duplicate forecast ID")
            identities.add(row["forecast_id"])
            try:
                items = list(packets(row))
            except (ValueError, KeyError, TypeError) as exc:
                skipped.append(dict(forecast_id=row["forecast_id"], reason=str(exc)))
                continue
            for p in items:
                events.extend([(stamp(p["origin"]), 1, p["id"], p), (stamp(p["due"]), 0, p["id"], p)])
        for when, kind, identity, packet in sorted(events, key=lambda e: e[:3]):
            if kind:
                engine.predict(packet, when)
            else:
                engine.resolve(identity, bar_loader(packet), when)
        report = engine.report()
        report.update(skipped=skipped, interpretation="Origin-time simulation on latest recorded candles; not actual historical River availability, not a sealed test")
        atomic_json(folder/"report.json", report)
        return report


def live_cycle(engine, output, start, now, reader=None):
    """Single worker observes durable stores; it never calls Kronos or Webull."""
    now = stamp(now)
    # Resolve existing pending forecasts before predicting newly observed ones.
    pending = sorted((p for p in engine.predictions.values() if p["id"] not in engine.outcomes), key=lambda p: (stamp(p["due"]), p["id"]))
    cache = {}
    def bars(p):
        key = (p["symbol"], packet_date(p))
        if key not in cache:
            cache[key] = recorded_bars(output, *key)
        return cache[key]
    for p in pending:
        if now >= stamp(p["due"]):
            available = bars(p)
            # Allow 90 seconds for the recorder. Afterwards missing is final.
            if outcome(p, available, now)["quality"] == "incomplete" and now < stamp(p["due"])+pd.Timedelta(seconds=90):
                continue
            engine.resolve(p["id"], available, now)
    incoming = reader.read() if reader is not None else read_forecasts(Path(output)/"forecasts.jsonl")
    if reader is not None:
        # A forecast can be appended after this cycle's clock was captured.
        reader.deferred.extend(r for r in incoming if r.get("forecast_created_at") and stamp(r["forecast_created_at"]) > now)
    rows = [r for r in incoming if r.get("source") == "webull_official" and r.get("forecast_created_at") and start <= stamp(r["forecast_created_at"]) <= now]
    for row in sorted(rows, key=lambda r: (stamp(r["forecast_created_at"]), r["forecast_id"])):
        if row["forecast_id"] in engine.rejections:
            continue
        # Avoid rebuilding features for the growing history every two seconds.
        if all(hashlib.sha256(f'{row["forecast_id"]}|{h}'.encode()).hexdigest() in engine.predictions for h in range(1, 6)):
            continue
        try:
            items = list(packets(row))
        except (ValueError, KeyError, TypeError) as exc:
            engine._commit("rejection", dict(forecast_id=row["forecast_id"], reason=str(exc)), now)
            continue
        for p in items:
            engine.predict(p, now)
    report = engine.report()
    report.update(status="running", updated_at=now.isoformat(),
                  late_predictions=sum(p["eligibility"] != "eligible" for p in engine.predictions.values()),
                  oldest_pending_due=min((p["due"] for p in engine.predictions.values() if p["id"] not in engine.outcomes), default=None),
                  latest_predictions=list(engine.predictions.values())[-500:])
    atomic_json(engine.folder/"status.json", report)
    return report


def panel(output, forecast_id=None):
    """Read-only API; works even when River isn't installed or has crashed."""
    path = Path(output)/"river_live"/"status.json"
    if not path.exists():
        return dict(status="disabled", groups=[], predictions=[], message="River worker is not running. Historical replay is required before live learning.")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        stale = (pd.Timestamp.now(tz="UTC")-stamp(result["updated_at"])).total_seconds()>30
        if stale:
            result["status"] = "stale / worker stopped"
        result["predictions"] = [p for p in result.pop("latest_predictions", []) if p["forecast_id"] == forecast_id]
        return result
    except (OSError, ValueError, KeyError):
        return dict(status="unavailable", groups=[], predictions=[])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("replay", "live"))
    parser.add_argument("--lab-output", type=Path, default=Path("data/kronos_lab"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--start", help="Replay first date, inclusive")
    parser.add_argument("--end", help="Replay last date, inclusive")
    parser.add_argument("--replay-report", type=Path, help="Completed technical replay gate for live worker")
    args = parser.parse_args()
    if args.mode == "replay":
        if not args.start or not args.end or not args.output:
            parser.error("replay requires --start, --end and a fresh --output")
        if args.start > args.end or (args.start <= "2026-07-31" and args.end >= "2026-07-01"):
            parser.error("Invalid range or protected July 2026")
        rows = [r for r in read_forecasts(args.lab_output/"forecasts.jsonl") if r.get("source") == "webull_official" and args.start <= stamp(r["last_input_timestamp"]).tz_convert("America/New_York").strftime("%Y-%m-%d") <= args.end]
        cache = {}
        def loader(p):
            key = (p["symbol"], packet_date(p))
            if key not in cache:
                cache[key] = recorded_bars(args.lab_output, *key)
            return cache[key]
        result = replay(rows, loader, args.output)
        print(json.dumps({k: result[k] for k in ("predictions", "observations", "quality_counts")}, indent=2))
        return
    if not args.replay_report:
        parser.error("Run replay first and supply --replay-report; live learning is opt-in")
    gate = json.loads(args.replay_report.read_text(encoding="utf-8"))
    if gate.get("version") != VERSION or gate.get("mode") != "replay" or gate.get("observations", 0) < 1:
        parser.error("Replay gate has no eligible observations or incompatible version")
    folder = args.lab_output/"river_live"
    with single_writer(folder):
        config_path = folder/"run.json"
        if not config_path.exists():
            atomic_json(config_path, dict(start=pd.Timestamp.now(tz="UTC").isoformat(), version=VERSION,
                                         replay_report=str(args.replay_report.resolve())))
        config = json.loads(config_path.read_text(encoding="utf-8"))
        engine = Engine(folder, "live")
        reader = ForecastTail(args.lab_output/"forecasts.jsonl")
        while True:
            began = time.perf_counter()
            try:
                live_cycle(engine, args.lab_output, stamp(config["start"]), pd.Timestamp.now(tz="UTC"), reader)
            except Exception as exc:
                atomic_json(folder/"status.json", dict(status="failed", error=type(exc).__name__,
                            updated_at=pd.Timestamp.now(tz="UTC").isoformat(), groups=[], latest_predictions=[]))
                raise
            # Worker timing is separate from deterministic research records.
            atomic_json(folder/"timing.json", dict(cycle_seconds=time.perf_counter()-began))
            time.sleep(2)


if __name__ == "__main__":
    main()
