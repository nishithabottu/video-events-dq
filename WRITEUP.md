# Data Quality POC

**Charter Video Insights SWE Case Study**
**Nishitha Bottu Ramakanthchowdray - May 26, 2026**

## Summary

I built a Python-based data quality engine that runs 16 rules across six categories against the video events sample, producing structured JSON findings and a plain-English Markdown report with LLM-generated explanations. The validation harness I designed achieves 100% recall on every critical-severity rule. The three findings with the greatest downstream impact are 88 duplicate event_ids inflating every aggregation, 27 null content_ids on playback events breaking the QoE Scorecard per-title rollup, and 173 unpaired session events corrupting the Session Duration Trends dashboard.

## How I Organized the Approach

The first thing I did was read the data dictionary carefully before touching the data. What stood out was that it didn't just describe the schema, it named the downstream systems that depend on it. That shifted how I framed the problem. Instead of asking "which rows are invalid," I asked "which invalid rows will break something someone cares about." That led me to add a `downstream_impact` field to every rule, mapping each check to the specific dashboard or metric it protects. That field is what makes a finding actionable rather than just informational.

From there I designed the system around five clear responsibilities: a loader that handles all type coercion and timestamp parsing, a rule registry where every check is a named declarative object with severity and impact metadata, a deterministic engine that runs the full registry and emits structured findings, an LLM explainer that converts each finding into a paragraph an analyst can read without knowing Python, and a reporter that assembles the final Markdown output. The key architectural decision was strict separation between detection and explanation, the engine runs deterministically first, and the LLM only touches the output after findings are finalized. That means the LLM cannot affect what gets flagged, only how it's described.

## How I Used AI in the Process

I used Claude Code as a development tool throughout the build. Before writing any rules, I used it to cross-check my initial list of DQ categories against what the data and dictionary actually supported, a way of pressure-testing my own taxonomy before committing to it. During implementation I worked through the codebase module by module, using Claude Code to accelerate writing and refining each component while keeping full ownership of every design decision.

At runtime, the system calls the Anthropic API inside `llm/explainer.py` using forced tool use, so every model response is validated against a predefined JSON schema before it touches any downstream logic. Each call is logged with model name, token counts, latency, and cost. I intentionally kept the model name as a single constant so that swapping to AWS Bedrock for a production deployment requires changing one line.

## How I Validated the Solution

Validation was something I planned from the start rather than added at the end. I wrote `eval/seed.py` to generate a clean synthetic baseline and inject a known set of labeled violations across every rule category, with `random.seed(42)` so the benchmark produces identical results on every run. `eval/score.py` then runs the engine against that seeded dataset and reports precision and recall per rule. Current results: 100% recall on all critical-severity rules. My personal threshold before I'd consider anything production-ready is 95%, anything below that is a bug, not a tuning issue.

I also wrote pytest unit tests for every rule covering both a valid and an invalid row, so no rule can regress silently. For the LLM layer, full per-call logging means explanation quality, latency, and cost are all observable over time.

## AI Best Practices Applied

A few things I was intentional about: forced tool use with a JSON schema on every LLM call so malformed output is structurally impossible; prompt templates versioned as `.md` files in the repository so any prompt change is a diff that can be reviewed and rolled back; a reproducible eval harness with a pinned random seed so benchmark comparisons are meaningful; and per-call observability logging so regressions in quality or cost surface before they become problems in production. The most important practice is the one baked into the architecture, the LLM has no role in detection. It only generates explanations after the deterministic engine has already produced its findings. Any future capability where the LLM proposes new rules would require explicit human approval before those rules could enter the registry.
