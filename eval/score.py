import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from rules.registry import REGISTRY
import rules.checks                                       # ← Triggers rule registration

def load_seeded(csv_path):
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    df['duration_ms'] = pd.to_numeric(df['duration_ms'], errors='coerce').astype('Int64')
    return df

def score(seeded_csv='eval/seeded.csv', gt_path='eval/ground_truth.json'):
    df = load_seeded(seeded_csv)
    ground_truth = json.loads(Path(gt_path).read_text())

    expected_by_rule = defaultdict(set)                   # ← Build answer key per rule
    for event_id, rule_id in ground_truth.items():
        if rule_id != 'clean':
            expected_by_rule[rule_id].add(event_id)

    results = []
    for rule in REGISTRY:
        bad_indices = rule.check(df)
        detected = set(df.loc[bad_indices, 'event_id'].tolist())
        expected = expected_by_rule.get(rule.id, set())
        tp = len(detected & expected)                     # ← Caught the seeded violation
        fp = len(detected - expected)                     # ← Flagged a clean row
        fn = len(expected - detected)                     # ← Missed a seeded violation
        precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else None
        recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else None
        results.append({
            'rule_id': rule.id, 'severity': rule.severity,
            'expected': len(expected), 'detected': len(detected),
            'tp': tp, 'fp': fp, 'fn': fn,
            'precision': precision, 'recall': recall
        })
    return results

def print_table(results):
    print(f"\n{'Rule':<12} {'Severity':<10} {'Exp':>4} {'Det':>4} {'TP':>3} {'FP':>3} {'FN':>3} {'Precision':>10} {'Recall':>8}")
    print('-' * 70)
    for r in results:
        p = f"{r['precision']:.2f}" if r['precision'] is not None else '   -'
        rec = f"{r['recall']:.2f}" if r['recall'] is not None else '   -'
        print(f"{r['rule_id']:<12} {r['severity']:<10} {r['expected']:>4} {r['detected']:>4} {r['tp']:>3} {r['fp']:>3} {r['fn']:>3} {p:>10} {rec:>8}")

if __name__ == '__main__':
    results = score()
    print_table(results)
    Path('eval/eval_results.json').write_text(json.dumps(results, indent=2))

    # ─── Aggregate: critical-severity recall (the target Katie cares about) ───
    crit = [r for r in results if r['severity'] == 'critical' and r['expected'] > 0]
    if crit:
        avg = sum(r['recall'] for r in crit) / len(crit)
        verdict = 'PASS' if avg >= 0.95 else 'MISS'
        print(f"\nCritical-severity average recall: {avg:.1%}  (target >= 95%, verdict: {verdict})")
