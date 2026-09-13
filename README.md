# Meridian

Process-mining analytics over a real event log (BPI Challenge 2017). Meridian rebuilds how the
process actually runs, diagnoses where it breaks down, simulates fixes, and produces an
executive business case with ROI shown as ranges.

> Status: Module A (process discovery) is complete, on the command line and in the web app.
> Modules B–F are next. See `07-PROGRESS-STATE.md`.

## Quickstart (current state)

Requirements: Python 3.11+, Node.js 20+, PostgreSQL 16+.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install

# PostgreSQL (macOS/Homebrew shown): one database for real runs, one for tests
brew install postgresql@18 && brew services start postgresql@18
/opt/homebrew/opt/postgresql@18/bin/createdb meridian
/opt/homebrew/opt/postgresql@18/bin/createdb meridian_test

# Download and checksum-verify the raw event log (~30 MB) into data/raw/
.venv/bin/python -m meridian.datasets

# Ingest: parse the XES, normalize, write data/processed/, load PostgreSQL (~16 s)
.venv/bin/python -m meridian.ingestion          # add --no-db to skip PostgreSQL

# Process discovery (Module A) in one command: ingests first if needed, then writes the
# process map, mined model, variant table, per-case statistics and a written summary
.venv/bin/python -m meridian.discovery                    # --reingest, --no-db available

# ...or each step on its own
.venv/bin/python -m meridian.discovery.dfg                # directly-follows graph -> dfg_edges.csv
.venv/bin/python -m meridian.discovery.heuristic_miner    # mined model -> heuristic_net.json

# Tests: fast suite (what the pre-commit hook runs), then everything incl. real-data tests
.venv/bin/pytest -m "not integration"
.venv/bin/pytest

# API: http://127.0.0.1:8000/health and /docs (serves the outputs written by meridian.discovery)
.venv/bin/uvicorn meridian.api.main:app --reload

# Frontend: http://localhost:3000 opens the process discovery view. It calls the API from the
# server side; set MERIDIAN_API_URL if the API is not at http://127.0.0.1:8000
cd frontend && npm install && npm run dev
```

## Configuration

All settings live in `backend/meridian/config.py` and can be overridden by environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MERIDIAN_DATA_DIR` | `./data` | Raw and processed data location |
| `MERIDIAN_DATABASE_URL` | `postgresql://localhost:5432/meridian` | Database for real runs |
| `MERIDIAN_TEST_DATABASE_URL` | `postgresql://localhost:5432/meridian_test` | Database tests may wipe |
| `MERIDIAN_LIFECYCLE_TRANSITIONS` | `complete` | Transitions kept in the normalized log (`all` keeps every one) |
| `MERIDIAN_DEPENDENCY_THRESHOLD` | `0.9` | Evidence an edge needs to enter the mined model, strictly between 0 and 1 |

## Layout

| Path | Contents |
|---|---|
| `backend/meridian/` | Python package — one subpackage per analytical module |
| `backend/meridian/ingestion/` | XES parsing, normalization, PostgreSQL storage |
| `frontend/` | Next.js app |
| `tests/` | pytest suite |
| `data/raw/`, `data/processed/` | Downloaded and derived data (not committed) |

## Ingestion outputs

| Output | Contents |
|---|---|
| `data/processed/raw_events.csv` | Every parsed event, all lifecycle transitions |
| `data/processed/event_log.csv` | Normalized log: `case_id, event_index, activity, timestamp, resource, cost, outcome` |
| `data/processed/ingestion_report.json` | Counts kept, filtered and excluded, by reason |
| `data/processed/dfg_edges.csv` | Directly-follows edges: frequency, case frequency, median and mean duration |
| `data/processed/heuristic_net.json` | Mined model: start/end activities and edges tagged by the rule that admitted them |
| `data/processed/dfg.mmd` | Mermaid process map of the most frequent directly-follows edges |
| `data/processed/variants.csv` | Every variant with case count, share and cumulative share |
| `data/processed/case_statistics.csv` | Per case: cycle time, activity count, variant rank, happy-path flag, outcome |
| `data/processed/discovery_summary.md` | Written Module A summary: variant headline, cycle-time p50/p90/p99, map, loops, caveats |
| PostgreSQL `event_log`, `ingestion_run` | Normalized log, and one audit row per ingestion run |

## Data

BPI Challenge 2017, 4TU.ResearchData, DOI
[10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b](https://doi.org/10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b),
distributed under the 4TU General Terms of Use. It is downloaded by the script above, never
committed.
