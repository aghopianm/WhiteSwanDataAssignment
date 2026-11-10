"""
Challenge 1 - Data Scraping.

Scrapes track information, race details and race times from the Swiftbet racing
page and stores the result in a DataFrame named ``df_races_data`` which is then
exported to ``data/df_races_data.csv``.

The Swiftbet racing page is a JavaScript SPA whose live race data is served by an
AWS AppSync GraphQL endpoint (``https://racing.apollo.ext.thebetmakers.com/query``).
That endpoint requires authentication (AppSync API key or Cognito JWT) and returns
HTTP 403 without valid credentials.

This module:
  1. Downloads the public track/meeting slugs asset.
  2. Calls the racing GraphQL endpoint for today + tomorrow (when credentials are
     available) and builds ``df_races_data``.
  3. Falls back gracefully with a clear, actionable error when live access is not
     configured, so the rest of the pipeline (bot + UI) can still be demonstrated.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from config import (
    APPSYNC_API_KEY,
    DATA_DIR,
    DEFAULT_HEADERS,
    MEETINGS_ASSETS_URL,
    RACES_COLUMNS,
    RACES_CSV,
    RACING_GRAPHQL_URL,
    SCRAPE_DATES,
    SwiftbetAuthError,
    TODAY,
    TOMORROW,
)

REQUEST_TIMEOUT = 30


# ---------------------------------------------------------------------------
# GraphQL client
# ---------------------------------------------------------------------------
class SwiftbetGraphQLClient:
    """Minimal client for the Swiftbet racing AppSync GraphQL endpoint."""

    def __init__(self, url: str = RACING_GRAPHQL_URL, api_key: Optional[str] = None):
        self.url = url
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if api_key:
            self.session.headers.update({"x-api-key": api_key})

    def execute(self, query: str, variables: Optional[dict] = None) -> dict:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        try:
            resp = self.session.post(self.url, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise SwiftbetAuthError(
                f"Unable to reach Swiftbet racing GraphQL endpoint ({self.url}): {exc}"
            ) from exc

        if resp.status_code == 403:
            raise SwiftbetAuthError(
                "Swiftbet racing GraphQL endpoint returned HTTP 403 Forbidden. "
                "Live race data requires AppSync authentication. "
                "Set SWIFTBET_APPSYNC_API_KEY (AppSync API key) or supply valid "
                "Cognito credentials, see README.md."
            )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise SwiftbetAuthError(
                f"Swiftbet GraphQL returned errors: {data['errors']}"
            )
        return data.get("data", {})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fetch_meeting_slugs() -> dict:
    """
    Download the public meetings asset.

    Returns a dict mapping meeting-slug -> reference string. This gives us the
    catalogue of tracks Swiftbet offers (Australia + NZ), which is useful for
    validating track names discovered on the racing page.
    """
    resp = requests.get(MEETINGS_ASSETS_URL, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _approx_race_time(minutes_to_start) -> Optional[str]:
    """Approximate the race clock time from a minutes-to-start value."""
    if minutes_to_start is None:
        return None
    try:
        mins = int(minutes_to_start)
    except (TypeError, ValueError):
        return None
    approx = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=mins)
    return approx.strftime("%H:%M")

# ---------------------------------------------------------------------------
# Challenge 1: build df_races_data
# ---------------------------------------------------------------------------
def scrape_races(api_key: Optional[str] = None) -> pd.DataFrame:
    """
    Scrape today's and tomorrow's races from Swiftbet.

    Returns a DataFrame named ``df_races_data`` with one row per race and
    persists it to ``data/df_races_data.csv``.

    Columns
    -------
    scraped_at, meeting_date, country, track_name, meeting_slug, race_number,
    race_id, race_slug, race_url, race_time, minutes_to_start, race_status
    """
    client = SwiftbetGraphQLClient(api_key=api_key or APPSYNC_API_KEY)

    rows = []
    # NOTE: the exact GraphQL operation names/fields depend on the Swiftbet
    # AppSync schema (introspection is disabled, so the queries below are the
    # shape the calls should take). Update QUERY_MEETINGS_BY_DATE / QUERY_RACE
    # to match the real schema once credentials are available.
    for meeting_date in SCRAPE_DATES:
        date_str = meeting_date.isoformat()
        try:
            data = client.execute(
                query=QUERY_MEETINGS_BY_DATE,
                variables={"date": date_str},
            )
        except SwiftbetAuthError:
            # Re-raise auth errors so the caller knows live access is missing.
            raise
        except Exception as exc:  # noqa: BLE001
            # Any other failure (network, unexpected schema) is reported clearly.
            raise SwiftbetAuthError(
                f"Failed to fetch races for {date_str}: {exc}"
            ) from exc

        meetings = (
            data.get("meetingsByDate", {}) or data.get("meetings", {}) or {}
        )
        for _country, country_meetings in meetings.items():
            for meeting in country_meetings or []:
                track_name = meeting.get("trackName") or meeting.get("track", {}).get("name")
                meeting_slug = meeting.get("slug") or meeting.get("meetingSlug")
                country = meeting.get("country")
                for race in meeting.get("races", []) or []:
                    race_number = race.get("raceNumber")
                    race_slug = race.get("slug") or race.get("raceSlug")
                    race_id = race.get("id") or race.get("raceId")
                    # Race time is approximated from the time-to-race-start value
                    # exposed on the page (countdown in minutes).
                    minutes_to_start = race.get("minutesToStart") or race.get("minutes_to_start")
                    race_time = _approx_race_time(minutes_to_start)
                    rows.append({
                        "scraped_at": now_iso(),
                        "meeting_date": date_str,
                        "country": country,
                        "track_name": track_name,
                        "meeting_slug": meeting_slug,
                        "race_number": race_number,
                        "race_id": race_id,
                        "race_slug": race_slug,
                        "race_url": (
                            f"{RACING_PAGE_ROOT}/{meeting_slug}/{race_slug}"
                            if meeting_slug and race_slug
                            else None
                        ),
                        "race_time": race_time,
                        "minutes_to_start": minutes_to_start,
                        "race_status": race.get("status"),
                    })

    df_races_data = pd.DataFrame(rows, columns=RACES_COLUMNS)

    # Persist to CSV.
    import os

    os.makedirs(DATA_DIR, exist_ok=True)
    df_races_data.to_csv(RACES_CSV, index=False)
    return df_races_data


# ---------------------------------------------------------------------------
# GraphQL operation templates (to be matched to the real Swiftbet schema)
# ---------------------------------------------------------------------------
QUERY_MEETINGS_BY_DATE = """
query MeetingsByDate($date: String!) {
  meetingsByDate(date: $date) {
    country
    trackName
    slug
    races {
      id
      raceId
      raceNumber
      slug
      raceSlug
      status
      minutesToStart
      startTime
    }
  }
}
"""

QUERY_RACE_CARD = """
query RaceCard($meetingSlug: String!, $raceSlug: String!) {
  raceCard(meetingSlug: $meetingSlug, raceSlug: $raceSlug) {
    raceNumber
    raceSlug
    runners {
      runnerId
      name
      tabNo
      silkUrl
      marketPrice
      marketType
    }
  }
}
"""


RACING_PAGE_ROOT = "https://www.swiftbet.com.au/racing"


if __name__ == "__main__":
    try:
        df = scrape_races()
        print(f"Scraped {len(df)} races -> {RACES_CSV}")
        print(df.head().to_string())
    except SwiftbetAuthError as exc:
        print(f"AUTH REQUIRED: {exc}")
        print("Configure SWIFTBET_APPSYNC_API_KEY or supply credentials to run live.")
