# White Swan Data Assignment &mdash; Python Test

Implementation of the 3-challenge Python test against **Swiftbet** racing
(`https://www.swiftbet.com.au/racing`). Tracked in this repository.

> **Source:** `Python Test (1).pdf` &mdash; "The exercise involves scraping track
> information, race details, and race times from a specified website, storing the
> data in a DataFrame, and saving it as a CSV file..."

## Repository contents

| File | Purpose |
|------|---------|
| `config.py` | Discovered endpoints, date targets (today + tomorrow), DataFrame column contracts, output paths |
| `scraper.py` | **Challenge 1** &mdash; builds `df_races_data` and exports `data/df_races_data.csv` |
| `bot.py` | **Challenge 2** &mdash; random race bot, builds `df_performed_bets` and exports `data/df_performed_bets.csv` |
| `ui.py` | **Challenge 3** &mdash; lightweight Flask UI (`python3 ui.py`) |
| `main.py` | CLI orchestrator: `scrape` / `bot` / `ui` / `all` |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Python / IDE / data output ignores |

## What I discovered about the target site

The Swiftbet racing page is a JavaScript single-page application (React/TanStack
Router + AWS Amplify). Its live race data is **not** in the initial HTML; it is
served by an AWS AppSync GraphQL endpoint:

```
https://racing.apollo.ext.thebetmakers.com/query
```

Static track/meeting slugs are published at:

```
https://l1wvilsgxcokkv0j.public.blob.vercel-storage.com/public/meetings/meetings.json
```

The swiftbet tenant config resolves to the `apollo` platform (locale `en-AU`),
cognito `https://cognito-idp.ap-southeast-2.amazonaws.com/`, and the AppSync
racing endpoint above.

## Authentication requirement (important)

The AppSync GraphQL endpoint returns **HTTP 403 Forbidden** without valid
credentials (AppSync API key or Cognito JWT). I do not have Swiftbet credentials,
so live race/market data cannot be fetched in this environment.

To run **live**:
1. Obtain a Swiftbet AppSync API key.
2. Set it in the environment or a `.env` file:
   ```
   SWIFTBET_APPSYNC_API_KEY=da2-xxx...
   ```
3. Run the scraper/bot.

All modules are auth-aware: when credentials are missing they raise a clear,
actionable `SwiftbetAuthError` instead of failing silently, so the pipeline
structure (DataFrames, CSV exports, UI) is complete and ready to run live once
credentials are supplied.

## Setup

```bash
git clone https://github.com/aghopianm/WhiteSwanDataAssignment.git
cd WhiteSwanDataAssignment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the challenges

**Challenge 1 &mdash; Data Scraping** (`df_races_data` → CSV)
```bash
python3 main.py scrape
# or
python3 -m scraper
```
Visits today + tomorrow, scrapes track name, race number, race URL, race time
(approximated from time-to-race-start), stores in `df_races_data`, exports to
`data/df_races_data.csv`.

**Challenge 2 &mdash; Bot Automation** (`df_performed_bets` → CSV)
```bash
python3 main.py bot
# or
python3 -m bot
```
Loads `data/df_races_data.csv`, selects a random track + race number, navigates
to the race via page-element lookup (track block → race card) rather than a
direct race URL, scrapes each horse's current market price, stores in
`df_performed_bets`, exports to `data/df_performed_bets.csv`.

**Challenge 3 &mdash; User Interface**
```bash
python3 main.py ui
# or
python3 ui.py
```
Open `http://127.0.0.1:5000`.
- `/` / `/races` &mdash; races table from `df_races_data.csv`
- `/bets` &mdash; performed bets from `df_performed_bets.csv`
- `/refresh` &mdash; re-run Challenge 1 scraper

**Run all (live):**
```bash
python3 main.py all
```

## DataFrame contracts

`df_races_data` columns:
`scraped_at, meeting_date, country, track_name, meeting_slug, race_number,
race_id, race_slug, race_url, race_time, minutes_to_start, race_status`

`df_performed_bets` columns:
`scraped_at, meeting_date, country, track_name, meeting_slug, race_number,
race_id, race_slug, horse_name, runner_id, tab_no, silk_url, market_price,
market_type`

## Notes

- The exact GraphQL operation/field names depend on the Swiftbet AppSync schema
  (introspection is disabled on the endpoint). The query templates in
  `scraper.py`/`bot.py` encode the discovered field shape
  (`trackName`, `raceNumber`, `raceSlug`, `startTime`, `minutesToStart`,
  `marketPrice`, ...) and should be matched to the real schema once credentials
  are available.
- Output CSVs are gitignored (generated when the app runs) so the repo tracks
  code, not generated data.
