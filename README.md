# Operon

Operon is a market-aware event intelligence system for prediction markets.

It scans event markets, selects high-quality modeling candidates, extracts structured evidence, updates event probabilities, and compares model beliefs against market-implied probabilities.

## Core Principle

LLMs do not directly forecast probabilities. They convert public information into structured observations. Probabilistic models perform the updates.

## MVP Modules

- Market Scout: scans Polymarket markets and ranks modeling candidates.
- Event Normalizer: converts markets into canonical event objects.
- Model Router: selects an event-specific probabilistic model.
- Evidence Ledger: stores structured observations and source lineage.
- Probability Engine: updates beliefs with log-odds and model-specific methods.
- Market Comparison: compares Operon posterior probability with market price.

## Layout

```text
backend/
  app/
    api/
    core/
    models/
    schemas/
    services/
    workers/
  tests/
frontend/
scripts/
docs/
```

## Quickstart

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```
