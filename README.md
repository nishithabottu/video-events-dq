# Video Events Data Quality POC

A Python data-quality engine for video playback events (Charter Video Insights case study). Deterministic rules detect; an LLM explains. The LLM is never on the detection critical path.

## Run it
```bash
pip3 install pandas pytest
python3 engine.py video_events_sample.csv findings.json   # → structured findings
python3 reporter.py findings.json findings_report.md      # → Markdown report
python3 eval/score.py                                     # → precision/recall per rule
```
Live LLM explanations: `pip3 install anthropic && export ANTHROPIC_API_KEY=... && python3 reporter.py findings.json findings_report.md --live`.

## What to look at
- `findings_report.md` — human-readable report (start here).
- `findings.json` — machine-readable findings, one row per rule.
- `WRITEUP.md` — 1-page write-up: approach, AI usage, validation, best practices.

## Architecture
```
loader → rules/registry → engine → findings.json → reporter → findings_report.md
                                                       └─ llm/explainer (structured-output, logged)
```

## Top 3 findings by downstream blast radius
- **UNIQ_001** (88) — duplicate event_ids double-count every aggregation; biases the >15% anomaly alert.
- **NULL_001** (27) — null content_id on playback breaks the QoE Scorecard's per-title rollup.
- **REF_001 + REF_002** (173) — unpaired playback_start/end events corrupt Session Duration Trends.

## AI best practices
Structured outputs via forced tool use · prompt templates versioned in git · reproducible eval harness (`random.seed(42)`) — 100% recall on critical-severity rules.
