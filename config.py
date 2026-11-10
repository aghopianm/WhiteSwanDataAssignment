"""
Configuration for the White Swan Data Assignment (Swiftbet racing scraper).

Endpoint discovery (performed by inspecting the swiftbet.com.au racing SPA):
- The racing page is a JavaScript single-page application. Its race/meeting data is
  served by an AWS AppSync GraphQL endpoint:
      https://racing.apollo.ext.thebetmakers.com/query
  This endpoint requires authentication (AppSync API key or Cognito JWT). Without
  valid credentials it returns HTTP 403.
- Static track/meeting slugs are published at:
      https://l1wvilsgxcokkv0j.public.blob.vercel-storage.com/public/meetings/meetings.json

Set SWIFTBET_APPSYNC_API_KEY in the environment (or a .env file) to enable live
GraphQL access. See README.md for details.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Discovered Swiftbet (Apollo / Betmakers) platform endpoints
# ---------------------------------------------------------------------------
SWIFTBET_RACING_PAGE = "https://www.swiftbet.com.au/racing"
RACING_GRAPHQL_URL = os.getenv(
    "SWIFTBET_RACING_GRAPHQL_URL",
    "https://racing.apollo.ext.thebetmakers.com/query",
)
MEETINGS_ASSETS_URL = os.getenv(
    "SWIFTBET_MEETINGS_ASSETS_URL",
    "https://l1wvilsgxcokkv0j.public.blob.vercel-storage.com"
    "/public/meetings/meetings.json",
)

# Optional AppSync API key for live GraphQL access.
APPSYNC_API_KEY = os.getenv("SWIFTBET_APPSYNC_API_KEY")

# ---------------------------------------------------------------------------
# Dates to cover: today and tomorrow (per the assignment requirement)
# ---------------------------------------------------------------------------
TODAY: date = date.today()
TOMORROW: date = TODAY + timedelta(days=1)
SCRAPE_DATES = [TODAY, TOMORROW]

# ---------------------------------------------------------------------------
# Output files & DataFrame column contracts
# ---------------------------------------------------------------------------
DATA_DIR = "data"
RACES_CSV = os.path.join(DATA_DIR, "df_races_data.csv")
BETS_CSV = os.path.join(DATA_DIR, "df_performed_bets.csv")

RACES_COLUMNS = [
    "scraped_at",
    "meeting_date",
    "country",
    "track_name",
    "meeting_slug",
    "race_number",
    "race_id",
    "race_slug",
    "race_url",
    "race_time",
    "minutes_to_start",
    "race_status",
]

BETS_COLUMNS = [
    "scraped_at",
    "meeting_date",
    "country",
    "track_name",
    "meeting_slug",
    "race_number",
    "race_id",
    "race_slug",
    "horse_name",
    "runner_id",
    "tab_no",
    "silk_url",
    "market_price",
    "market_type",
]

# Headers used when calling Swiftbet endpoints.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
}


class SwiftbetAuthError(RuntimeError):
    """Raised when Swiftbet live endpoints cannot be reached due to auth."""


__all__ = [
    "SWIFTBET_RACING_PAGE",
    "RACING_GRAPHQL_URL",
    "MEETINGS_ASSETS_URL",
    "APPSYNC_API_KEY",
    "TODAY",
    "TOMORROW",
    "SCRAPE_DATES",
    "DATA_DIR",
    "RACES_CSV",
    "BETS_CSV",
    "RACES_COLUMNS",
    "BETS_COLUMNS",
    "DEFAULT_HEADERS",
    "SwiftbetAuthError",
]
