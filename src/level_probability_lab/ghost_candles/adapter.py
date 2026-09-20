from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file



DEFAULT_KRONOS_ROOT = Path(r"C:\Users\ruley\Kronos")
DEFAULT_MODEL_ID = "NeoQuasar/Kronos-small"
DEFAULT_TOKENIZER_ID = "NeoQuasar/Kronos-Tokenizer-base"
SMALL_MODEL_REVISION = "901c26c1332695a2a8f243eb2f37243a37bea320"
BASE_TOKENIZER_REVISION = "0e0117387f39004a9016484a186a908917e22426"
MINI_MODEL_ID = "NeoQuasar/Kronos-mini"
MINI_TOKENIZER_ID = "NeoQuasar/Kronos-Tokenizer-2k"
MINI_MODEL_REVISION = "f4e68697d9d5aed55cef5c96aabc3376bcad9f81"
MINI_TOKENIZER_REVISION = "26966d0035065a0cae0ebad7af8ece35bc1fb51c"


def make_kronos_forecaster(which: str = "small", **kwargs) -> "KronosPathForecaster":
    which = which.lower().replace("_", "-")
    if which in {"mini", "kronos-mini"}:
        kwargs.setdefault("model_id", MINI_MODEL_ID)
        kwargs.setdefault("tokenizer_id", MINI_TOKENIZER_ID)
        kwargs.setdefault("model_revision", MINI_MODEL_REVISION)
        kwargs.setdefault("tokenizer_revision", MINI_TOKENIZER_REVISION)
    else:
        kwargs.setdefault("model_id", DEFAULT_MODEL_ID)
        kwargs.setdefault("tokenizer_id", DEFAULT_TOKENIZER_ID)
        kwargs.setdefault("model_revision", SMALL_MODEL_REVISION)
        kwargs.setdefault("tokenizer_revision", BASE_TOKENIZER_REVISION)
    return KronosPathForecaster(**kwargs)


def _ensure_kronos_path(kronos_root: Path) -> None:
    root = str(kronos_root)
    if root not in sys.path:
        sys.path.insert(0, root)


def _infer_all_paths(
    tokenizer,
    model,
    x,
    x_stamp,
    y_stamp,
    max_context,
    pred_len,
    clip,
    temperature,
    top_k,
    top_p,
    sample_count,
):
    """Kronos auto-regressive sampling without averaging paths.

    Upstream `auto_regressive_inference` returns the mean over samples.
    This copy keeps every path. Kronos source is not modified.
    """
    from model.kronos import sample_from_logits

    with torch.no_grad():
        x = torch.clip(x, -clip, clip)
        device = x.device
        x = x.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, x.size(1), x.size(2)).to(device)
        x_stamp = x_stamp.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, x_stamp.size(1), x_stamp.size(2)).to(device)
        y_stamp = y_stamp.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, y_stamp.size(1), y_stamp.size(2)).to(device)

        x_token = tokenizer.encode(x, half=True)
        initial_seq_len = x.size(1)
        batch_size = x_token[0].size(0)
        total_seq_len = initial_seq_len + pred_len
        full_stamp = torch.cat([x_stamp, y_stamp], dim=1)

        generated_pre = x_token[0].new_empty(batch_size, pred_len)
        generated_post = x_token[1].new_empty(batch_size, pred_len)
        pre_buffer = x_token[0].new_zeros(batch_size, max_context)
        post_buffer = x_token[1].new_zeros(batch_size, max_context)
        buffer_len = min(initial_seq_len, max_context)
        if buffer_len > 0:
            start_idx = max(0, initial_seq_len - max_context)
            pre_buffer[:, :buffer_len] = x_token[0][:, start_idx : start_idx + buffer_len]
            post_buffer[:, :buffer_len] = x_token[1][:, start_idx : start_idx + buffer_len]

        for i in range(pred_len):
            current_seq_len = initial_seq_len + i
            window_len = min(current_seq_len, max_context)
            if current_seq_len <= max_context:
                input_tokens = [pre_buffer[:, :window_len], post_buffer[:, :window_len]]
            else:
                input_tokens = [pre_buffer, post_buffer]
            context_end = current_seq_len
            context_start = max(0, context_end - max_context)
            current_stamp = full_stamp[:, context_start:context_end, :].contiguous()
            s1_logits, context = model.decode_s1(input_tokens[0], input_tokens[1], current_stamp)
            s1_logits = s1_logits[:, -1, :]
            sample_pre = sample_from_logits(s1_logits, temperature=temperature, top_k=top_k, top_p=top_p, sample_logits=True)
            s2_logits = model.decode_s2(context, sample_pre)
            s2_logits = s2_logits[:, -1, :]
            sample_post = sample_from_logits(s2_logits, temperature=temperature, top_k=top_k, top_p=top_p, sample_logits=True)
            generated_pre[:, i] = sample_pre.squeeze(-1)
            generated_post[:, i] = sample_post.squeeze(-1)
            if current_seq_len < max_context:
                pre_buffer[:, current_seq_len] = sample_pre.squeeze(-1)
                post_buffer[:, current_seq_len] = sample_post.squeeze(-1)
            else:
                pre_buffer.copy_(torch.roll(pre_buffer, shifts=-1, dims=1))
                post_buffer.copy_(torch.roll(post_buffer, shifts=-1, dims=1))
                pre_buffer[:, -1] = sample_pre.squeeze(-1)
                post_buffer[:, -1] = sample_post.squeeze(-1)

        full_pre = torch.cat([x_token[0], generated_pre], dim=1)
        full_post = torch.cat([x_token[1], generated_post], dim=1)
        context_start = max(0, total_seq_len - max_context)
        input_tokens = [
            full_pre[:, context_start:total_seq_len].contiguous(),
            full_post[:, context_start:total_seq_len].contiguous(),
        ]
        z = tokenizer.decode(input_tokens, half=True)
        z = z.reshape(-1, sample_count, z.size(1), z.size(2))
        preds = z.cpu().numpy()
        return preds[:, :, -pred_len:, :]


class KronosPathForecaster:
    """Isolated Kronos wrapper. Load once, keep on GPU, return all sample paths."""

    def __init__(
        self,
        *,
        kronos_root: Path = DEFAULT_KRONOS_ROOT,
        model_id: str = DEFAULT_MODEL_ID,
        tokenizer_id: str = DEFAULT_TOKENIZER_ID,
        model_revision: str = SMALL_MODEL_REVISION,
        tokenizer_revision: str = BASE_TOKENIZER_REVISION,
        device: str = "cuda:0",
        max_context: int = 512,
        clip: float = 5.0,
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 0,
        cache_dir: Path | None = None,
    ) -> None:
        if not device.startswith("cuda"):
            raise RuntimeError(f"refusing non-CUDA device {device!r}")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available; aborting rather than CPU fallback")
        _ensure_kronos_path(Path(kronos_root))
        from model import Kronos, KronosTokenizer

        self.model_name = model_id
        self.model_revision = model_revision
        self.tokenizer_name = tokenizer_id
        self.tokenizer_revision = tokenizer_revision
        self.device = device
        self.max_context = max_context
        self.clip = clip
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k

        tok_cfg = json.loads(
            Path(hf_hub_download(tokenizer_id, "config.json", revision=tokenizer_revision, local_files_only=True, cache_dir=cache_dir)).read_text(
                encoding="utf-8"
            )
        )
        model_cfg = json.loads(
            Path(hf_hub_download(model_id, "config.json", revision=model_revision, local_files_only=True, cache_dir=cache_dir)).read_text(
                encoding="utf-8"
            )
        )
        tokenizer = KronosTokenizer(**tok_cfg)
        tokenizer.load_state_dict(
            load_file(
                hf_hub_download(tokenizer_id, "model.safetensors", revision=tokenizer_revision, local_files_only=True, cache_dir=cache_dir),
                device=device,
            )
        )
        model = Kronos(**model_cfg)
        model.load_state_dict(
            load_file(
                hf_hub_download(model_id, "model.safetensors", revision=model_revision, local_files_only=True, cache_dir=cache_dir),
                device=device,
            )
        )
        self.tokenizer = tokenizer.to(device).eval()
        self.model = model.to(device).eval()

    def forecast_paths(self, window: pd.DataFrame, future_ts, sample_count: int, seed: int):
        from model.kronos import calc_time_stamps

        torch.manual_seed(int(seed))
        torch.cuda.manual_seed_all(int(seed))
        df = window[["open", "high", "low", "close", "volume"]].copy()
        df["amount"] = (window["amount"].astype(np.float64) if "amount" in window
                        else df["volume"].astype(np.float64) * df["close"].astype(np.float64))
        if not np.isfinite(df["amount"]).all() or (df["amount"] <= 0).any():
            raise ValueError("Invalid traded-dollar input")
        x_ts = pd.to_datetime(window["bar_start"], utc=True).dt.tz_convert("America/New_York")
        y_index = pd.DatetimeIndex(future_ts)
        if y_index.tz is None:
            y_index = y_index.tz_localize("UTC")
        y_ts = pd.Series(y_index.tz_convert("America/New_York"))
        x_stamp = calc_time_stamps(x_ts).values.astype(np.float32)
        y_stamp = calc_time_stamps(y_ts).values.astype(np.float32)
        x = df[["open", "high", "low", "close", "volume", "amount"]].values.astype(np.float32)
        x_mean, x_std = np.mean(x, axis=0), np.std(x, axis=0)
        x_norm = np.clip((x - x_mean) / (x_std + 1e-5), -self.clip, self.clip)

        x_t = torch.from_numpy(x_norm[np.newaxis, :]).to(self.device)
        x_stamp_t = torch.from_numpy(x_stamp[np.newaxis, :]).to(self.device)
        y_stamp_t = torch.from_numpy(y_stamp[np.newaxis, :]).to(self.device)

        torch.cuda.synchronize()
        t0 = time.perf_counter()
        with torch.no_grad():
            preds = _infer_all_paths(
                self.tokenizer,
                self.model,
                x_t,
                x_stamp_t,
                y_stamp_t,
                self.max_context,
                pred_len=len(future_ts),
                clip=self.clip,
                temperature=self.temperature,
                top_k=self.top_k,
                top_p=self.top_p,
                sample_count=sample_count,
            )
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0
        # preds: (1, S, T, 6) normalized
        denorm = preds * (x_std + 1e-5) + x_mean
        ohlc = denorm[0, :, :, :4].astype(np.float64)
        return ohlc, elapsed
