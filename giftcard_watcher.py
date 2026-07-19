"""
Gift card watcher for MTS Spotify (payment.mts.ru/tools/spotify)
--------------------------------------------------------------------------
Uses a real (headless) browser via Playwright to select each country in
the region dropdown, exactly like a real user would, then reads the
visible "sold out" marker text on the rendered page. This avoids calling
the site's protected API directly (which is guarded by anti-fraud tokens
we can't and shouldn't forge).

Sends ONE Telegram message daily with the current status of each
configured country, regardless of whether anything changed.

Designed to be run ONCE per invocation by a scheduler (GitHub Actions).

Required environment variables (set as GitHub Actions secrets):
  BOT_TOKEN  - your Telegram bot token
  CHAT_ID    - your Telegram chat id

Optional environment variable (set as a GitHub Actions *variable*):
  COUNTRIES  - comma-separated list of exact option labels as they
               appear in the dropdown, e.g.:
               "Польша Польша,США США,Франция Франция,Италия Италия"
               Defaults to those four if not set.
"""

import os
import sys
import json
import requests
from playwright.sync_api import sync_playwright

SPOTIFY_URL = "https://payment.mts.ru/tools/spotify"
NETFLIX_URL = "https://payment.mts.ru/tools/netflix"
SOLD_OUT_MARKER = "РАСКУПИЛИ"
STATUS_FILE = "status.json"
REGION_BUTTON_NAME = "Выбрать регион"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DEFAULT_COUNTRIES = "Польша Польша,США США,Франция Франция,Италия Италия,Турция Турция,Европа Европа"
COUNTRIES = [
    c.strip()
    for c in os.environ.get("COUNTRIES", DEFAULT_COUNTRIES).split(",")
    if c.strip()
]


def send_telegram_message(text: str) -> None:
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(api_url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    resp.raise_for_status()


def read_previous_statuses() -> dict:
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_statuses(statuses: dict) -> None:
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(statuses, f, indent=2, ensure_ascii=False)


def check_country_status(page, country_option_name: str) -> str:
    page.get_by_role("button", name=REGION_BUTTON_NAME).click()
    page.get_by_role("option", name=country_option_name).click()
    page.wait_for_timeout(2500)  # let the price/availability data load after selection
    content = page.content()
    return "sold_out" if SOLD_OUT_MARKER in content else "available"


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID environment variables.")
        sys.exit(1)

    previous = read_previous_statuses()
    current = {}
    lines = []
    for PAGE_URL in [SPOTIFY_URL, NETFLIX_URL]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(PAGE_URL)
            page.wait_for_timeout(2000)

            for country in COUNTRIES:
                try:
                    status = check_country_status(page, country)
                except Exception as e:
                    print(f"Error checking {country}: {e}")
                    current[country] = previous.get(country, "unknown")
                    lines.append(f"{country}: check failed ({e})")
                    continue

                current[country] = status
                prev_status = previous.get(country, "unknown")
                changed = prev_status not in ("unknown", status)
                print(f"{country}: previous={prev_status} current={status}")

                emoji = "✅" if status == "available" else "❌"
                label = "AVAILABLE" if status == "available" else "sold out"
                line = f"{emoji} {country}: {label}"
                if changed:
                    line += "  (changed since last check)"
                lines.append(line)

            browser.close()

        message = "Daily gift card status:\n" + "\n".join(lines) + f"\n{PAGE_URL}"
        send_telegram_message(message)
    print("Daily status message sent.")

    write_statuses(current)


if __name__ == "__main__":
    main()