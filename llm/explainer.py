import os, json, time, hashlib, sys
from pathlib import Path

PROMPT_PATH = Path(__file__).parent / "prompts" / "explain_finding.md"
LOG_PATH = Path(__file__).parent / "call_log.jsonl"
MODEL = "claude-sonnet-4-5-20250929"                       # ← Swap to bedrock model id for AWS

# ── Structured-output contract: every LLM call returns THIS shape ──
EXPLANATION_TOOL = {
    "name": "submit_explanation",
    "description": "Submit the structured explanation of a data quality finding",
    "input_schema": {
        "type": "object",
        "properties": {
            "explanation":         {"type": "string"},
            "severity_rationale":  {"type": "string"},
            "suggested_owner":     {"type": "string"},
            "confidence":          {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["explanation", "severity_rationale", "suggested_owner", "confidence"]
    }
}

def explain_finding(finding, dry_run=False):
    if dry_run:
        return _canned(finding)                            # ← Offline fallback for demo

    from anthropic import Anthropic                        # ← Lazy import: not needed in dry-run
    prompt = PROMPT_PATH.read_text().replace("{{FINDING}}", json.dumps(finding, indent=2))
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]

    client = Anthropic()                                   # ← Reads ANTHROPIC_API_KEY env var
    t0 = time.time()
    resp = client.messages.create(
        model=MODEL, max_tokens=512,
        tools=[EXPLANATION_TOOL],
        tool_choice={"type": "tool", "name": "submit_explanation"},   # ← FORCED structured output
        messages=[{"role": "user", "content": prompt}]
    )
    latency_ms = int((time.time() - t0) * 1000)
    tool_block = next(b for b in resp.content if b.type == "tool_use")
    result = tool_block.input

    _log_call(finding["rule_id"], prompt_hash, resp.usage, latency_ms, result)
    return result

# ── Rule-specific plain-English narratives used when the LLM is offline. ──
# These are written for a non-engineer Director: state the violation,
# name the dashboard that breaks, recommend an action.
_CANNED_EXPLANATIONS = {
    "UNIQ_001": {
        "explanation": "{count} event_ids appear more than once. Because every aggregation joins on event_id, these duplicates inflate play counts and bias the 7-day rolling baseline used by the >15% anomaly alert — analysts will chase phantom spikes. Action: dedupe at ingest before session_metrics_daily is built.",
        "owner": "Video Insights ingest team",
    },
    "NULL_001": {
        "explanation": "{count} playback events are missing content_id. The QoE Scorecard groups buffer ratio and play counts by title — these rows fall out of the rollup entirely, so the content team cannot see which titles are buffering. Action: make content_id NOT NULL on playback_start and playback_end at the schema level.",
        "owner": "STB / mobile client teams (source of the playback event)",
    },
    "NULL_002": {
        "explanation": "{count} events are missing device_id. Device-cohort analyses and the Platform Reliability report cannot attribute these events to a fleet, so platform-level error rates are under-counted. Action: reject events without device_id at the collector.",
        "owner": "STB / mobile client teams",
    },
    "NULL_003": {
        "explanation": "{count} non-error events carry an error_code. These spurious codes inflate the platform error rate and can trip the >15% anomaly alert with no real incident behind it. Action: clear error_code on non-error events at the transform step.",
        "owner": "Video Insights ingest team",
    },
    "ENUM_001": {
        "explanation": "{count} rows carry an error_code outside the documented E001–E010 set. These codes bucket into 'unknown' on the Platform Reliability dashboard, so root-cause counts under-report. Action: extend the catalog or fix the emitter, then backfill.",
        "owner": "Platform Reliability / device firmware team",
    },
    "RANGE_001": {
        "explanation": "{count} events have a negative duration_ms. Negative durations pull the average-session-duration metric below truth on the leadership Tableau scorecard. Action: clamp at the source or drop these rows in the daily rollup.",
        "owner": "STB / mobile client teams",
    },
    "RANGE_002": {
        "explanation": "{count} playback_start or buffer_start events carry a non-null duration. Start events should have no duration; including them double-counts time in the average-session-duration metric. Action: null duration_ms on start events in the transform.",
        "owner": "Video Insights ingest team",
    },
    "RANGE_003": {
        "explanation": "{count} events fall outside the trailing-30-day window expected by the 7-day rolling baseline. Out-of-window rows skew the baseline and can either mask real anomalies or trigger false ones on the >15% alert. Action: filter on event timestamp at the ingest boundary.",
        "owner": "Video Insights ingest team",
    },
    "FMT_001": {
        "explanation": "{count} rows have a firmware_version that does not match the documented X.Y.Z pattern. Device-cohort analyses in fleet-health reports cannot group these rows by version, so firmware-regressing rollouts are harder to detect. Action: normalize firmware strings at the collector.",
        "owner": "Device firmware team",
    },
    "REF_001": {
        "explanation": "{count} sessions have a playback_start with no matching playback_end. Without a paired end event, the Session Duration Trends dashboard cannot compute session length for these sessions, so average-session-duration is computed on a biased subset. Action: investigate client-side drop/crash paths and add an end-of-session sentinel.",
        "owner": "STB / mobile client teams",
    },
    "REF_002": {
        "explanation": "{count} sessions have an orphan playback_end with no playback_start. These show up as completed sessions of unknown length on the Session Duration Trends dashboard and corrupt the session-completion metric. Action: confirm whether starts are being dropped at the collector, then either backfill or filter orphans.",
        "owner": "Video Insights ingest team",
    },
    "REF_003": {
        "explanation": "{count} buffer_start events have no matching buffer_end in the same session. The QoE Scorecard's buffer-ratio metric depends on paired start/end events; unclosed buffers inflate buffering time. Action: emit a buffer_end on session teardown if one was missed.",
        "owner": "STB / mobile client teams",
    },
}

def _canned(finding):                                      # ← Deterministic stub for offline demo
    rule_id = finding["rule_id"]
    spec = _CANNED_EXPLANATIONS.get(rule_id)
    if spec:
        explanation = spec["explanation"].format(count=finding["count"])
        owner = spec["owner"]
    else:
        explanation = f"{finding['count']} rows violated {rule_id}: {finding['description']}. This affects: {finding['downstream_impact']}."
        owner = "Video Insights ingest team"
    return {
        "explanation": explanation,
        "severity_rationale": f"Severity '{finding['severity']}' reflects the downstream blast radius.",
        "suggested_owner": owner,
        "confidence": 0.85
    }

def _log_call(rule_id, prompt_hash, usage, latency_ms, result):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cost = (usage.input_tokens * 3 + usage.output_tokens * 15) / 1_000_000   # ← Sonnet 4.5 pricing
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({
            "rule_id": rule_id, "model": MODEL, "prompt_hash": prompt_hash,
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
            "latency_ms": latency_ms, "cost_usd": round(cost, 6),
            "result_preview": result["explanation"][:80]
        }) + "\n")

if __name__ == "__main__":
    findings_path = "findings.json"
    dry_run = "--dry-run" in sys.argv
    with open(findings_path) as f:
        findings = json.load(f)

    failed = [x for x in findings if x.get("status") == "failed"][:3]   # ← Demo on first 3
    for finding in failed:
        result = explain_finding(finding, dry_run=dry_run)
        print(f"\n─── {finding['rule_id']} ({finding['severity']}, {finding['count']} violations) ───")
        print(result["explanation"])
        print(f"Suggested owner: {result['suggested_owner']}  (confidence {result['confidence']})")
