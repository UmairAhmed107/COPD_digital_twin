# COPD Digital Twin — Research Prototype

**Status:** `src/data_prep.py` implemented and tested. All other
modules (`reliability.py`, `twin_state.py`, `model.py`,
`simulator.py`, `evaluation.py`) remain placeholders.

This is a research/engineering prototype exploring an AI-based digital
twin for COPD progression and personalized care. It is **not a
medical diagnostic or treatment system**.

Full design context lives in:

- `notes/architecture.md` — system architecture and module responsibilities (source of truth)
- `notes/novelty_notes.md` — technical directions under investigation for later prior-art review (not a patent claim)
- `notes/progress_log.md` — dated log of development sessions and decisions

## Project Rules

1. Follow `notes/architecture.md` as the source of truth.
2. Build one module at a time — do not implement the whole system at once.
3. Keep the proposed reliability-aware persistent twin state separate from baseline methods (simple replacement, exponential smoothing).
4. Do not claim anything is novel. Prior-art research is required before any such claim.
5. Document every important algorithmic decision (date, change, reason, expected effect, result).
6. This is a research prototype, not a medical diagnostic or treatment system.

## Project Structure

```text
copd-twin/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── synthetic/
│
├── src/
│   ├── data_prep.py      # Data ingestion & preparation (placeholder)
│   ├── reliability.py    # Observation quality/reliability assessment (placeholder)
│   ├── twin_state.py     # Twin State Module — core area under investigation (placeholder)
│   ├── model.py           # Progression model (not started — out of scope for now)
│   ├── simulator.py       # Counterfactual simulator (not started — out of scope for now)
│   └── evaluation.py      # Experimental validation (not started — out of scope for now)
│
├── dashboard/              # Not started
│
├── tests/                  # Structural tests for the placeholder modules
│
├── notes/
│   ├── architecture.md
│   ├── novelty_notes.md
│   └── progress_log.md
│
├── requirements.txt
└── README.md
```

## Current Development Stage

- Directory structure matching `notes/architecture.md` Section 12.
- `src/data_prep.py` is implemented: a dataset-agnostic pipeline
  (schema validation, missing-value handling, normalization,
  categorical encoding, timestamp attachment, and conversion to a
  consistent `Observation` format). No specific COPD dataset is
  assumed anywhere — callers supply a `DatasetSchema`. See
  `notes/progress_log.md` for full implementation details and open
  decisions.
- `reliability.py`, `twin_state.py`, `model.py`, `simulator.py`,
  `evaluation.py` remain placeholders (documented interfaces, raise
  `NotImplementedError`).
- No dataset has been chosen or loaded (see architecture.md Open Questions).
- No ML model, dashboard, counterfactual simulator, or hardware
  integration has been built.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Running Tests

```bash
pytest
```

All current tests verify that the placeholder modules import
correctly and that their stub functions explicitly raise
`NotImplementedError` (rather than silently doing nothing or
producing incorrect results).

## Next Steps

See `notes/progress_log.md` and `notes/architecture.md` Section 14
(Open Questions) for planned next steps. Development proceeds one
module at a time; the next module should not be started until
explicitly requested.
