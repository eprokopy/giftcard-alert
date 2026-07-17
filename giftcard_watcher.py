"""
Gift card restock watcher for payment.mts.ru/tools/spotify
------------------------------------------------------------
Designed to be run ONCE per invocation by a scheduler (GitHub Actions).
Remembers the last known status in status.txt (committed back to the
repo by the workflow) so it only notifies when the status actually
CHANGES from sold-out to available.

Required environment variables (set as GitHub Actions secrets):
  BOT_TOKEN  - your Telegram bot token
  CHAT_ID    - your Telegram chat id
"""

import os
import sys
import requests

URL = "https://payment.mts.ru/tools/spotify"
SOLD_OUT_MARKER = "РАСКУПИЛИ"
STATUS_FILE = "status.txt"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}


def send_telegram_message(text: str) -> None:
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(api_url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    resp.raise_for_status()


def read_previous_status() -> str:
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            return f.read().strip()
    return "unknown"


def write_status(status: str) -> None:
    with open(STATUS_FILE, "w") as f:
        f.write(status)


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID environment variables.")
        sys.exit(1)

    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    sold_out = SOLD_OUT_MARKER in resp.text
    current_status = "sold_out" if sold_out else "available"

    previous_status = read_previous_status()
    print(f"Previous: {previous_status} | Current: {current_status}")

    if previous_status == "sold_out" and current_status == "available":
        send_telegram_message(f"🎁 The Spotify gift card looks available again!\n{URL}")
        print("Notification sent.")

    write_status(current_status)


if __name__ == "__main__":
    main()
