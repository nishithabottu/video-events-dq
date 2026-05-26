# Data Quality POC — Writeup

**Charter Video Insights — AI-Focused SWE Case Study**
**Nishi Bhavsar — May 26, 2026**

## Summary

I built a Python data quality engine that runs 16 rules across 6 categories, outputs findings as JSON, and generates a plain-English Markdown report with LLM explanations. The three findings that matter most for your dashboards: 88 duplicate event_ids (inflates every aggregation), 27 null content_ids on playback events (breaks the QoE Scorecard per-title rollup), and 173 unpaired session events (corrupts Session Duration Trends). The eval harness I built to verify it hits 100% recall on all critical-severity rules.

## How I organized the approach

My first instinct was to write a quick script, but I held off. Once I saw the data dictionary listed downstream systems — the Tableau dashboards, the anomaly alerts, the session metrics table — I realized the real problem wasn't finding bad rows, it was knowing which bad rows actually matter to someone. So I added a `downstream_impact` field to every rule, naming the exact dashboard or metric it corrupts. That one field is what makes a finding useful to an analyst instead of just being a row count.

The architecture ended up with five pieces: a loader, a rule registry, a deterministic engine, an LLM explainer, and a reporter. The thing I'm most deliberate about is the split between the engine and the explainer — the engine always runs deterministically, the LLM only touches the output after findings are already written. That way a bad model response can never make a real issue disappear.

## How I used AI in the process

I used Claude at two stages. During discovery, before I wrote a single rule, I pasted the data dictionary and 50 sample rows and asked it to list every plausible data quality category it could see — specifically so I wasn't just confirming my own assumptions. It caught the firmware version format issue before I did. During build, I used it as a pair programmer, reviewing each module as I went rather than generating everything at once.

At runtime, the system calls the Anthropic API inside `llm/explainer.py` using forced tool use so every response comes back as a validated JSON object. Every call gets logged with the model, token counts, latency, and cost. I also made the model name a single constant so switching to Bedrock later is a one-line change.

## How I validated the solution

I built a small eval harness because I didn't want to just eyeball whether it worked. `eval/seed.py` takes a clean dataset and injects labeled violations across every rule category (seeded with `random.seed(42)` so it's reproducible), and `eval/score.py` measures precision and recall per rule against that ground truth. Current results: 100% recall on every critical-severity rule. I target ≥95% as a ship threshold — anything below that gets investigated before it goes anywhere near a production pipeline.

I also wrote pytest unit tests for each rule with both a passing and failing row, so a broken rule fails CI rather than silently shipping. For the LLM layer, every API call is logged with enough detail to detect if explanation quality drifts over time.

## AI best practices applied

A few things I was deliberate about: structured outputs with forced tool use on every LLM call so the parser never breaks; prompt templates kept as `.md` files in git so any change is a reviewable diff; the eval harness pinned to a fixed seed so results are comparable across runs; full per-call observability to catch cost or quality regressions early. Most importantly, the LLM is never in the detection path — it only explains findings after the deterministic engine has already written them. Any future rule the LLM suggests requires human review before it enters the registry.
