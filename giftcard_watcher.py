"""
Gift card watcher for MTS Spotify (payment.mts.ru/tools/spotify)
--------------------------------------------------------------------------
Calls the site's own pricing API directly (found via browser dev tools).
Checks a configurable list of service codes and sends ONE Telegram
message daily with the current status of each — sold out or available —
regardless of whether anything changed.

Designed to be run ONCE per invocation by a scheduler (GitHub Actions).

Required environment variables (set as GitHub Actions secrets):
  BOT_TOKEN     - your Telegram bot token
  CHAT_ID       - your Telegram chat id

Optional environment variable (set as a GitHub Actions *variable*, not
secret, so you can update it without touching the code):
  SERVICE_CODES - comma-separated list, e.g. "480,481,482"
                  Defaults to 480,481,482 if not set.
"""

import os
import sys
import json
import requests

API_URL = "https://api.mtsbank.ru/anonymous/games/getPrice"
PARTNER = "fwk"
STATUS_FILE = "status.json"
PAGE_URL = "https://payment.mts.ru/tools/spotify"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SERVICE_CODES = [
    int(code.strip())
    for code in os.environ.get("SERVICE_CODES", "480,481,482").split(",")
    if code.strip()
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": PAGE_URL,
    "Accept": "application/json",
}


def send_telegram_message(text: str) -> None:
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(api_url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    resp.raise_for_status()


def read_previous_statuses() -> dict:
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    return {}


def write_statuses(statuses: dict) -> None:
    with open(STATUS_FILE, "w") as f:
        json.dump(statuses, f, indent=2)


def check_service_code(code: int) -> tuple[str, str]:
    """Returns (status, price) for a given serviceCode."""
    params = {"serviceCode": code, "partner": PARTNER}
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    price = data.get("price", "")
    status = "available" if price else "sold_out"
    return status, price


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID environment variables.")
        sys.exit(1)

    previous = read_previous_statuses()
    current = {}
    lines = []

    for code in SERVICE_CODES:
        code_key = str(code)
        try:
            status, price = check_service_code(code)
        except requests.RequestException as e:
            print(f"Error checking code {code}: {e}")
            current[code_key] = previous.get(code_key, "unknown")
            lines.append(f"Code {code}: check failed ({e})")
            continue

        current[code_key] = status
        prev_status = previous.get(code_key, "unknown")
        changed = prev_status not in ("unknown", status)
        print(f"Code {code}: previous={prev_status} current={status} price={price!r}")

        if status == "available":
            line = f"✅ Code {code}: AVAILABLE (price {price})"
        else:
            line = f"❌ Code {code}: sold out"
        if changed:
            line += "  (changed since last check)"
        lines.append(line)

    message = "Daily gift card status:\n" + "\n".join(lines) + f"\n{PAGE_URL}"
    send_telegram_message(message)
    print("Daily status message sent.")

    write_statuses(current)


if __name__ == "__main__":
    main()