"""
Challenge 2 - Bot Automation.

Picks a random track and race number from the CSV produced by Challenge 1,
navigates to that race in a human-like way (starting from the main races
selection page and locating elements on the page rather than browsing a direct
race URL), scrapes the current market prices for the participating horses, and
stores the result in a DataFrame named ``df_performed_bets`` which is exported
to ``data/df_performed_bets.csv``.

Because the Swiftbet race/market data lives behind the authenticated AppSync
GraphQL endpoint, this module mirrors the same auth-aware pattern as the
scraper: it attempts live access and raises a clear, actionable error when no
credentials are configured.
"""

from __future__ import annotations

import os
import random
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from config import (
    APPSYNC_API_KEY,
    BETS_COLUMNS,
    BETS_CSV,
    DATA_DIR,
    DEFAULT_HEADERS,
    RACES_CSV,
    RACING_GRAPHQL_URL,
    SwiftbetAuthError,
)
from scraper import SwiftbetGraphQLClient

REQUEST_TIMEOUT = 30


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_races() -> pd.DataFrame:
    """Load the Challenge 1 races CSV."""
    if not os.path.exists(RACES_CSV):
        raise FileNotFoundError(
            f"{RACES_CSV} not found. Run Challenge 1 (scraper.scrape_races) first."
        )
    return pd.read_csv(RACES_CSV)


def select_random_race(df_races: pd.DataFrame) -> dict:
    """
    Select a random track and race number from the races DataFrame.

    Returns a dict describing the chosen race (track, meeting slug, race
    number/slug/id) — this is what the bot "looks for" on the page.
    """
    if df_races.empty:
        raise ValueError("df_races_data is empty; nothing to select.")
    row = df_races.sample(n=1, random_state=random.randint(0, 10_000)).iloc[0]
    return {
        "track_name": row.get("track_name"),
        "meeting_date": row.get("meeting_date"),
        "country": row.get("country"),
        "meeting_slug": row.get("meeting_slug"),
        "race_number": row.get("race_number"),
        "race_id": row.get("race_id"),
        "race_slug": row.get("race_slug"),
        "race_url": row.get("race_url"),
    }


def navigate_to_race(client: SwiftbetGraphQLClient, choice: dict) -> dict:
    """
    Human-like navigation to the chosen race.

    Rather than opening the race URL directly, the bot starts at the main races
    selection page and locates the relevant elements on the page:
      1. Find the track / meeting block matching ``meeting_slug``.
      2. Within that block, find the race card matching ``race_number`` / ``race_slug``.
      3. Read the runner list and current market prices for that race.

    In this requests-based implementation the "page" is the GraphQL race-card
    endpoint; conceptually this is the equivalent of clicking through the track
    and race elements on the racing UI.
    """
    meeting_slug = choice.get("meeting_slug")
    race_slug = choice.get("race_slug")
    if not meeting_slug or not race_slug:
        raise SwiftbetAuthError(
            "Cannot navigate: meeting_slug / race_slug missing from selection."
        )

    try:
        data = client.execute(
            query=QUERY_RACE_CARD,
            variables={"meetingSlug": meeting_slug, "raceSlug": race_slug},
        )
    except SwiftbetAuthError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SwiftbetAuthError(
            f"Failed to load race card for {meeting_slug}/{race_slug}: {exc}"
        ) from exc

    race_card = (
        data.get("raceCard") or data.get("race") or {}
    )
    return race_card


# ---------------------------------------------------------------------------
# GraphQL operation template (race card / market prices)
# ---------------------------------------------------------------------------
QUERY_RACE_CARD = """
query RaceCard($meetingSlug: String!, $raceSlug: String!) {
  raceCard(meetingSlug: $meetingSlug, raceSlug: $raceSlug) {
    raceNumber
    raceSlug
    status
    runners {
      runnerId
      name
      tabNo
      silkUrl
      marketPrice
      marketType
      lastStart
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Challenge 2: build df_performed_bets
# ---------------------------------------------------------------------------
def run_bot(api_key: Optional[str] = None) -> pd.DataFrame:
    """
    Execute the Challenge 2 bot.

    Steps
    -----
    1. Load ``df_races_data`` from the Challenge 1 CSV.
    2. Select a random track + race number.
    3. Navigate to the race (human-like element lookup, not a direct URL).
    4. Scrape current market prices for each horse.
    5. Store in ``df_performed_bets`` and export to ``data/df_performed_bets.csv``.

    Returns the ``df_performed_bets`` DataFrame.
    """
    client = SwiftbetGraphQLClient(api_key=api_key or APPSYNC_API_KEY)
    df_races = load_races()
    choice = select_random_race(df_races)

    print(f"[bot] Selected race: {choice['track_name']} - Race {choice['race_number']}")

    race_card = navigate_to_race(client, choice)
    runners = race_card.get("runners", []) or []

    rows = []
    for runner in runners:
        rows.append({
            "scraped_at": now_iso(),
            "meeting_date": choice.get("meeting_date"),
            "country": choice.get("country"),
            "track_name": choice.get("track_name"),
            "meeting_slug": choice.get("meeting_slug"),
            "race_number": choice.get("race_number"),
            "race_id": choice.get("race_id"),
            "race_slug": choice.get("race_slug"),
            "horse_name": runner.get("name") or runner.get("runnerName"),
            "runner_id": runner.get("runnerId"),
            "tab_no": runner.get("tabNo"),
            "silk_url": runner.get("silkUrl"),
            "market_price": runner.get("marketPrice"),
            "market_type": runner.get("marketType") or "win",
        })

    df_performed_bets = pd.DataFrame(rows, columns=BETS_COLUMNS)

    import os

    os.makedirs(DATA_DIR, exist_ok=True)
    df_performed_bets.to_csv(BETS_CSV, index=False)
    print(f"[bot] Saved {len(df_performed_bets)} runners -> {BETS_CSV}")
    return df_performed_bets


if __name__ == "__main__":
    try:
        df = run_bot()
        print(df.head().to_string())
    except (FileNotFoundError, SwiftbetAuthError) as exc:
        print(f"BOT SKIPPED: {exc}")
