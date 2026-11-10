"""
White Swan Data Assignment &mdash; entry point.

Usage:
    python3 main.py scrape    # Challenge 1: scrape races -> df_races_data.csv
    python3 main.py bot       # Challenge 2: bot -> df_performed_bets.csv
    python3 main.py ui        # Challenge 3: launch the Flask UI
    python3 main.py all       # scrape + bot (live mode)

Live mode requires Swiftbet AppSync credentials. Set
SWIFTBET_APPSYNC_API_KEY in the environment or a .env file (see README.md).
"""
from __future__ import annotations

import sys

from bot import run_bot
from config import APPSYNC_API_KEY
from scraper import scrape_races
from ui import app


def cmd_scrape() -> None:
    try:
        df = scrape_races()
        print(f"\nChallenge 1 complete: {len(df)} races -> data/df_races_data.csv")
    except Exception as exc:  # noqa: BLE001
        print(f"\nChallenge 1 failed: {exc}")
        sys.exit(1)


def cmd_bot() -> None:
    try:
        df = run_bot()
        print(f"\nChallenge 2 complete: {len(df)} runners -> data/df_performed_bets.csv")
    except Exception as exc:  # noqa: BLE001
        print(f"\nChallenge 2 failed: {exc}")
        sys.exit(1)


def cmd_ui() -> None:
    print("\nStarting Challenge 3 UI at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 0
    command = argv[0].lower()
    if command == "scrape":
        cmd_scrape()
    elif command == "bot":
        cmd_bot()
    elif command == "ui":
        cmd_ui()
    elif command == "all":
        cmd_scrape()
        cmd_bot()
    else:
        print(f"Unknown command: {command}")
        print("Available: scrape, bot, ui, all")
        return 1
    return 0


if __name__ == "__main__":
    # Credentials hint
    if not APPSYNC_API_KEY:
        print("Note: SWIFTBET_APPSYNC_API_KEY not set &mdash; live mode will "
              "report an auth error (expected without credentials).")
    raise SystemExit(main())
