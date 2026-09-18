from __future__ import annotations

import sys

from level_probability_lab.exceptions import EnvironmentMismatch

PROJECT_VENV_MARKERS = ("aistcockprobabilitydoctor", ".venv")
REQUIRED_DEVICE_TOKEN = "5070"
REQUIRED_TORCH_CUDA_TOKEN = "cu128"
REQUIRED_CUDA_VERSION_PREFIX = "12.8"


def collect_env() -> dict:
    import torch

    cuda_ok = bool(torch.cuda.is_available())
    device_name = torch.cuda.get_device_name(0) if cuda_ok else ""
    return {
        "executable": sys.executable,
        "python_version": sys.version.split()[0],
        "torch_version": torch.__version__,
        "torch_cuda": str(torch.version.cuda or ""),
        "cuda_available": cuda_ok,
        "device_name": device_name,
        "device_count": int(torch.cuda.device_count()) if cuda_ok else 0,
    }


def validate_env(env: dict) -> dict:
    exe = (env.get("executable") or "").replace("\\", "/").lower()
    if not all(token in exe for token in PROJECT_VENV_MARKERS):
        raise EnvironmentMismatch(
            f"must use the project venv (AiStcockProbabilitydoctor/.venv); got {env.get('executable')!r}"
        )
    if not env.get("cuda_available"):
        raise EnvironmentMismatch("CUDA is required; refusing CPU fallback")
    torch_version = env.get("torch_version") or ""
    torch_cuda = str(env.get("torch_cuda") or "")
    has_cu128 = REQUIRED_TORCH_CUDA_TOKEN in torch_version or torch_cuda.startswith(REQUIRED_CUDA_VERSION_PREFIX)
    if not has_cu128:
        raise EnvironmentMismatch(
            f"expected official cu128 / CUDA 12.8 build; got torch={torch_version!r} cuda={torch_cuda!r}"
        )
    device_name = env.get("device_name") or ""
    if REQUIRED_DEVICE_TOKEN not in device_name:
        raise EnvironmentMismatch(f"expected RTX 5070; got {device_name!r}")
    return env


def require_cuda_env() -> dict:
    env = collect_env()
    print("ghost-candle env:")
    print(f"  sys.executable           = {env['executable']}")
    print(f"  torch.__version__        = {env['torch_version']}")
    print(f"  torch.version.cuda       = {env['torch_cuda']}")
    print(f"  torch.cuda.get_device_name(0) = {env['device_name']}")
    return validate_env(env)
