# Data Quality POC — Writeup

**Charter Video Insights — AI-Focused SWE Case Study**
**Nishi Bhavsar — May 26, 2026**

## Summary

Built a Python data-quality engine for the video playback events sample. It runs **16 declarative rules** across 6 categories, emits structured findings as JSON, renders a Markdown report with LLM-generated explanations, and ships with a seeded ground-truth eval harness. **The eval shows 100% recall on every critical-severity rule.** The three issues with the largest downstream blast radius are **UNIQ_001 (88 duplicate event_ids)**, **NULL_001 (27 null content_ids on playback)**, and **REF_001 + REF_002 (173 unpaired playback_start/end events)** — corrupting the >15% anomaly alert, the QoE Scorecard per-title rollup, and the Session Duration Trends dashboard respectively.

## How I organized the approach

I treated this as a governance problem, not a script. Five clean responsibilities: a **loader** that types the data, a **rule registry** where every check is a declarative `Rule` object carrying id, severity, description, and `downstream_impact`, a deterministic **engine** that iterates the registry and emits structured findings, an **LLM explainer** that turns each finding into a paragraph an analyst can act on, and a **reporter** that renders the final Markdown. The split between deterministic detection and LLM-driven explanation is intentional and is the architectural spine — the LLM never decides what is or isn't a finding.

The 16 rules are grouped into Schema/Type, Domain/Enum, Nullability, Range/Format, Uniqueness, and Referential/Session Integrity. Every rule carries a `downstream_impact` string naming the dashboard or metric it corrupts (QoE Scorecard, Session Duration Trends, Platform Reliability, the >15% anomaly alert). That single field is the bridge between an engineering finding and a business outcome — it's what makes a row in `findings.json` legible to a Director without translation.

## How I used AI in the process

Two distinct surfaces. At **build time**, Claude Code in the project repo acted as a pair programmer — I drove it through five phases (discovery, deterministic core, eval harness, LLM layer, polish), reviewing each module before moving on. At **runtime**, the system calls the Anthropic API directly inside `llm/explainer.py` with **forced tool use** for structured outputs, so every LLM response is a parser-safe JSON object matching a predefined schema. Each call is logged to `llm/call_log.jsonl` with model, prompt hash, input/output tokens, latency, and dollar cost. The model name is a single constant in `llm/explainer.py` — swapping to AWS Bedrock for a production deployment is a one-line change.

## How I validated the solution

The headline number: **100% recall on critical-severity rules** on a seeded ground-truth benchmark. The validation has three layers. **Unit tests:** `pytest` cases with paired positive/negative rows per rule, so a broken rule fails CI before it ships. **Dataset-level eval:** `eval/seed.py` generates clean rows plus labeled violations across every rule category with `random.seed(42)` for reproducibility, and `eval/score.py` computes precision and recall per rule against the ground truth. **LLM observability:** every API call is logged with cost and latency so output drift, latency regressions, and prompt regressions are detectable in production. I would not ship an AI tool I cannot measure.

## AI best practices applied

- **Structured outputs via forced tool use** — the model cannot return malformed JSON.
- **Prompt templates versioned in git** as `.md` files separate from code; a prompt change is a reviewable diff.
- **Eval harness with reproducible synthetic ground truth** (`random.seed(42)`) and per-rule precision/recall.
- **Per-call observability** (model, prompt hash, tokens, latency, cost) written to a JSONL log.
- **LLM strictly off the deterministic detection critical path** — same input always returns the same findings.
- **Human-in-the-loop** required before any future LLM-proposed rule enters the production registry.
