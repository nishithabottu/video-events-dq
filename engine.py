import json
import sys
from datetime import datetime, timezone
from loader import load_events
from rules.registry import REGISTRY
import rules.checks                                  # ← Triggers @register_rule

def run_checks(df):
    findings = []
    for rule in REGISTRY:
        try:
            bad_indices = rule.check(df)             # ← Run the rule
            status = "failed" if bad_indices else "passed"
            findings.append({
                "rule_id": rule.id,
                "category": rule.category,
                "severity": rule.severity,
                "description": rule.description,
                "downstream_impact": rule.downstream_impact,
                "status": status,
                "count": len(bad_indices),
                "sample_event_ids": df.loc[bad_indices[:5], 'event_id'].tolist(),
                "run_timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:                       # ← One bad rule can't kill the run
            findings.append({
                "rule_id": rule.id, "status": "error", "error": str(e),
                "run_timestamp": datetime.now(timezone.utc).isoformat()
            })
    return findings

if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'video_events_sample.csv'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'findings.json'

    df = load_events(csv_path)
    findings = run_checks(df)

    with open(out_path, 'w') as f:
        json.dump(findings, f, indent=2)

    failed = [f for f in findings if f.get('status') == 'failed']
    print(f"Ran {len(findings)} rules — {len(failed)} found violations — wrote {out_path}")
