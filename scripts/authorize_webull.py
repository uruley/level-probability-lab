"""Approve the lab .env Webull login. Does not read or change the scanner key."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, r"C:\Users\ruley\WebullTradingScanner")

from scanner.config import WebullConfig
from scanner.webull_client import OfficialWebullBackend
from webull_env import webull_credentials


def main():
    key, secret, token_dir = webull_credentials()
    if not key or not secret:
        raise SystemExit("WEBULL_APP_KEY and WEBULL_APP_SECRET are missing from this lab's .env")
    token_dir.mkdir(parents=True, exist_ok=True)
    cfg = WebullConfig(
        backend="official", use_production=True, region="us",
        app_key=key, app_secret=secret, token_dir=str(token_dir), max_retries=1)
    print("Approve the OpenAPI request in the Webull phone app. Waiting up to 5 minutes.")
    OfficialWebullBackend(cfg, r"C:\Users\ruley\WebullTradingScanner").connect(token_wait_seconds=300)
    print("SUCCESS")


if __name__ == "__main__":
    main()
