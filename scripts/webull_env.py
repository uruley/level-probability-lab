"""Lab Webull credentials. The project .env wins; the scanner fills gaps."""
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SCANNER = Path(r"C:\Users\ruley\WebullTradingScanner")


def webull_credentials():
    lab = dotenv_values(ROOT / ".env")
    scanner = dotenv_values(SCANNER / ".env")

    def pick(name):
        return (lab.get(name) or scanner.get(name) or "").strip()

    key = pick("WEBULL_APP_KEY")
    secret = pick("WEBULL_APP_SECRET")
    own = bool((lab.get("WEBULL_APP_KEY") or "").strip() and (lab.get("WEBULL_APP_SECRET") or "").strip())
    token_dir = ROOT / "data" / "kronos_lab" / "webull_token" if own else SCANNER / ".webull_token"
    return key, secret, token_dir
