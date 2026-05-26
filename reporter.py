import json, sys
from datetime import datetime, timezone
from llm.explainer import explain_finding

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

# ── Top-3 by downstream blast radius (not by raw count). ──
# Ordering choices: UNIQ_001 corrupts every aggregation; NULL_001 breaks the
# per-title QoE Scorecard rollup; REF_001+REF_002 corrupt the average-session-
# duration metric that shows on the leadership scorecard.
BLAST_RADIUS_TOP3 = ["UNIQ_001", "NULL_001", "REF_001"]

def render_report(findings, dry_run=True):
    failed = [f for f in findings if f.get("status") == "failed"]
    passed = [f for f in findings if f.get("status") == "passed"]
    failed.sort(key=lambda x: (SEVERITY_ORDER.get(x['severity'], 9), -x['count']))   # ← Worst first
    by_id = {f["rule_id"]: f for f in failed}

    lines = []
    lines.append(f"# Data Quality Report — Video Events\n")
    lines.append(f"_Generated {datetime.now(timezone.utc).isoformat()}_\n")

    # ─── Executive summary ───
    lines.append("## Executive Summary\n")
    lines.append(f"Ran **{len(findings)} rules** against the dataset. **{len(failed)} rules found violations**, {len(passed)} passed clean.\n")

    blast_radius_picks = [by_id[r] for r in BLAST_RADIUS_TOP3 if r in by_id]
    if blast_radius_picks:
        lines.append("**Top 3 issues by downstream blast radius:**\n")
        lines.append(f"- **UNIQ_001** (critical, {by_id['UNIQ_001']['count']} rows) — duplicate event_ids double-count every aggregation and bias the 7-day rolling baseline behind the >15% anomaly alert.")
        lines.append(f"- **NULL_001** (critical, {by_id['NULL_001']['count']} rows) — null content_id on playback drops rows from the QoE Scorecard's per-title rollup; the content team cannot see which titles are buffering.")
        ref1 = by_id.get('REF_001', {}).get('count', 0)
        ref2 = by_id.get('REF_002', {}).get('count', 0)
        lines.append(f"- **REF_001 + REF_002** (warning, {ref1 + ref2} rows combined) — unpaired playback_start/playback_end events corrupt the average-session-duration metric on the Session Duration Trends dashboard.")
        lines.append("")

    # ─── What this means for your dashboards (for Katie / non-engineers) ───
    lines.append("## What this means for your dashboards\n")
    lines.append(
        "Today's sample contains issues that touch every downstream surface the Video Insights team owns. "
        "The **Session Duration Trends** dashboard pulls from `session_metrics_daily`, which joins on event_id and pairs playback_start/playback_end — the duplicate event_ids (UNIQ_001) and the orphaned start/end events (REF_001, REF_002) both bias average session duration in different directions. "
        "The **QoE Scorecard** rolls up buffer ratio per title; null content_ids (NULL_001) drop rows from that rollup entirely, and unclosed buffer events (REF_003) inflate buffering time. "
        "The **Platform Reliability** report depends on a valid device_id and a documented error_code; nulls (NULL_002) and out-of-catalog codes (ENUM_001) under-count platform incidents. "
        "Finally, the **>15% anomaly alert** is keyed off a 7-day rolling baseline of these same aggregates — duplicates and out-of-window timestamps (RANGE_003) can either fire the alert with no real incident behind it or mask one that's actually happening. None of the corrupted metrics will surface as obviously wrong; analysts will chase phantom signals until the rules fail at ingest.\n"
    )

    # ─── Per-finding detail with LLM explanation ───
    lines.append("## Findings\n")
    for f in failed:
        explanation = explain_finding(f, dry_run=dry_run)                    # ← LLM narrates the finding
        lines.append(f"### {f['rule_id']} — {f['severity'].upper()} — {f['count']} violations\n")
        lines.append(f"**Rule:** {f['description']}  ")
        lines.append(f"**Category:** {f['category']}  ")
        lines.append(f"**Downstream impact:** {f['downstream_impact']}\n")
        lines.append(f"**Plain-English explanation:**  ")
        lines.append(f"> {explanation['explanation']}\n")
        lines.append(f"**Suggested owner:** {explanation['suggested_owner']}  ")
        lines.append(f"**Confidence:** {explanation['confidence']}  ")
        lines.append(f"**Sample event_ids:** `{', '.join(f.get('sample_event_ids', [])[:5])}`\n")

    # ─── Passed checks (still worth listing for governance) ───
    if passed:
        lines.append("## Passed Checks\n")
        for f in passed:
            lines.append(f"- **{f['rule_id']}** ({f['category']}) — {f['description']}")

    return "\n".join(lines)

if __name__ == "__main__":
    findings_path = "findings.json"
    out_path = "findings_report.md"
    dry_run = "--live" not in sys.argv                                        # ← Default dry-run

    with open(findings_path) as f:
        findings = json.load(f)
    report = render_report(findings, dry_run=dry_run)
    with open(out_path, "w") as f:
        f.write(report)
    print(f"Wrote {out_path} ({len(report)} chars, dry_run={dry_run})")
