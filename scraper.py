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
  3. Raises a clear, actionable error when live access is not configured.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
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
    SwiftbetAuthError,
    scrape_dates,
)

REQUEST_TIMEOUT = 30

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


# ---------------------------------------------------------------------------
# GraphQL client
# ---------------------------------------------------------------------------
class SwiftbetGraphQLError(SwiftbetAuthError):
    """Raised when the GraphQL endpoint returns a non-403 error response."""


class SwiftbetGraphQLClient:
    """Minimal client for the Swiftbet racing AppSync GraphQL endpoint.

    Network/transport errors are reported as ``SwiftbetGraphQLError``; HTTP 403
    (missing/invalid credentials) is reported as ``SwiftbetAuthError`` so callers
    can distinguish "no credentials configured" from "a request failed".
    """

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
            raise SwiftbetGraphQLError(
                f"Unable to reach Swiftbet racing GraphQL endpoint ({self.url}): {exc}"
            ) from exc

        if resp.status_code == 403:
            raise SwiftbetAuthError(
                "Swiftbet racing GraphQL endpoint returned HTTP 403 Forbidden. "
                "Live race data requires AppSync authentication. "
                "Set SWIFTBET_APPSYNC_API_KEY (AppSync API key) or supply valid "
                "Cognito credentials, see README.md."
            )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise SwiftbetGraphQLError(
                f"Swiftbet racing GraphQL endpoint returned HTTP "
                f"{resp.status_code}: {exc}"
            ) from exc
        data = resp.json()
        if "errors" in data:
            raise SwiftbetGraphQLError(
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


def _first(value, *alternatives):
    """Return value if not None/empty-string, else the first non-None alternative.

    Note: ``0`` is a legitimate value (e.g. minutes-to-start) and is preserved.
    """
    if value is not None and value != "":
        return value
    for alt in alternatives:
        if alt is not None and alt != "":
            return alt
    return None


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
    for meeting_date in scrape_dates():
        date_str = meeting_date.isoformat()
        try:
            data = client.execute(
                query=QUERY_MEETINGS_BY_DATE,
                variables={"date": date_str},
            )
        except SwiftbetAuthError:
            raise
        except SwiftbetGraphQLError as exc:
            raise SwiftbetAuthError(
                f"Failed to fetch races for {date_str}: {exc}"
            ) from exc

        country_map = (
            data.get("meetingsByDate", {}) or data.get("meetings", {}) or {}
        )
        for _country, country_meetings in country_map.items():
            for meeting in country_meetings or []:
                track_block = meeting.get("track") or {}
                track_name = meeting.get("trackName") or track_block.get("name")
                meeting_slug = meeting.get("slug") or meeting.get("meetingSlug")
                country = meeting.get("country")
                for race in meeting.get("races", []) or []:
                    race_number = race.get("raceNumber")
                    race_slug = race.get("slug") or race.get("raceSlug")
                    race_id = race.get("id") or race.get("raceId")
                    minutes_to_start = _first(
                        race.get("minutesToStart"), race.get("minutes_to_start")
                    )
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
    os.makedirs(DATA_DIR, exist_ok=True)
    df_races_data.to_csv(RACES_CSV, index=False)
    return df_races_data


if __name__ == "__main__":
    try:
        df = scrape_races()
        print(f"Scraped {len(df)} races -> {RACES_CSV}")
        print(df.head().to_string())
    except SwiftbetAuthError as exc:
        print(f"AUTH REQUIRED: {exc}")
        print("Configure SWIFTBET_APPSYNC_API_KEY or supply credentials to run live.")
