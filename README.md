# Meridian

Process-mining analytics over a real event log (BPI Challenge 2017). Meridian rebuilds how the
process actually runs, diagnoses where it breaks down, simulates fixes, and produces an
executive business case with ROI shown as ranges.

> Status: early build — infrastructure only. See `07-PROGRESS-STATE.md`.

## Quickstart (current state)

Requirements: Python 3.11+, Node.js 20+.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install

# Download and checksum-verify the raw event log (~30 MB) into data/raw/
.venv/bin/python -m meridian.datasets

# Tests (full suite)
.venv/bin/pytest

# API: http://127.0.0.1:8000/health
.venv/bin/uvicorn meridian.api.main:app --reload

# Frontend: http://localhost:3000
cd frontend && npm install && npm run dev
```

## Layout

| Path | Contents |
|---|---|
| `backend/meridian/` | Python package — one subpackage per analytical module |
| `frontend/` | Next.js app |
| `tests/` | pytest suite |
| `data/raw/`, `data/processed/` | Downloaded and derived data (not committed) |

## Data

BPI Challenge 2017, 4TU.ResearchData, DOI
[10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b](https://doi.org/10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b),
distributed under the 4TU General Terms of Use. It is downloaded by the script above, never
committed.
