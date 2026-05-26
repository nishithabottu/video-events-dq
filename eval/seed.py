import csv, json, uuid, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)                                          # ← Reproducible eval
NOW = datetime.now(timezone.utc)
PLATFORMS = ['roku', 'stva', 'specguide', 'odn', 'tve']
ERROR_CODES = [f'E{i:03d}' for i in range(1, 11)]

def _ts(offset_days=None, offset_seconds=0):
    days = random.randint(0, 25) if offset_days is None else offset_days
    return (NOW - timedelta(days=days) + timedelta(seconds=offset_seconds)).isoformat().replace('+00:00', 'Z')

def _clean_session():                                    # ← Paired playback start+end in one session
    sid = str(uuid.uuid4())
    did = f'device_{uuid.uuid4().hex[:8]}'
    plat = random.choice(PLATFORMS)
    cid = f'content_{random.randint(1,99):04d}'
    fw = random.choice(['12.1.3', '12.0.2', '11.4.0', '13.0.0'])
    days_ago = random.randint(0, 25)
    base = {'session_id': sid, 'platform': plat, 'content_id': cid, 'device_id': did, 'firmware_version': fw, 'error_code': ''}
    start = {**base, 'event_id': str(uuid.uuid4()), 'event_type': 'playback_start',
             'timestamp': _ts(days_ago, 0), 'duration_ms': ''}
    end = {**base, 'event_id': str(uuid.uuid4()), 'event_type': 'playback_end',
           'timestamp': _ts(days_ago, 300), 'duration_ms': str(random.randint(100_000, 5_000_000))}
    return [start, end]

def build_seed():
    rows, ground_truth = [], {}

    # 25 clean paired sessions = 50 clean rows
    for _ in range(25):
        for r in _clean_session():
            rows.append(r); ground_truth[r['event_id']] = 'clean'

    def add_bad(row, rule_id):
        rows.append(row); ground_truth[row['event_id']] = rule_id

    # UNIQ_001 — duplicate event_id
    dup_id = rows[0]['event_id']
    for _ in range(3):
        r = _clean_session()[0]; r['event_id'] = dup_id
        add_bad(r, 'UNIQ_001')

    # NULL_001 — content_id null on playback
    for _ in range(3):
        r = _clean_session()[0]; r['content_id'] = ''
        add_bad(r, 'NULL_001')

    # NULL_002 — device_id null
    for _ in range(2):
        r = _clean_session()[0]; r['device_id'] = ''
        add_bad(r, 'NULL_002')

    # ENUM_001 — invalid error_code
    for code in ['UNKNOWN', 'E999', 'ERR']:
        r = _clean_session()[0]; r['event_type'] = 'error'; r['duration_ms'] = '500'; r['error_code'] = code
        add_bad(r, 'ENUM_001')

    # RANGE_001 — negative duration_ms
    for _ in range(3):
        r = _clean_session()[1]; r['duration_ms'] = '-1000'
        add_bad(r, 'RANGE_001')

    # RANGE_002 — duration_ms on a start event
    for _ in range(2):
        r = _clean_session()[0]; r['duration_ms'] = '5000'
        add_bad(r, 'RANGE_002')

    # FMT_001 — bad firmware format
    for fw in ['12.1', 'v13.0.0']:
        r = _clean_session()[0]; r['firmware_version'] = fw
        add_bad(r, 'FMT_001')

    # ENUM_002 — invalid event_type
    r = _clean_session()[0]; r['event_type'] = 'click'; r['duration_ms'] = ''
    add_bad(r, 'ENUM_002')

    # ENUM_003 — invalid platform
    r = _clean_session()[0]; r['platform'] = 'android'
    add_bad(r, 'ENUM_003')

    # NULL_003 — error_code on non-error event
    r = _clean_session()[1]; r['error_code'] = 'E001'
    add_bad(r, 'NULL_003')

    # REF_001 — playback_start with no end (single-event session)
    for _ in range(2):
        r = _clean_session()[0]                          # ← Take only the start, drop the end
        add_bad(r, 'REF_001')

    # REF_002 — playback_end with no start
    for _ in range(2):
        r = _clean_session()[1]
        add_bad(r, 'REF_002')

    return rows, ground_truth

if __name__ == '__main__':
    rows, gt = build_seed()
    out_dir = Path('eval'); out_dir.mkdir(exist_ok=True)
    with open(out_dir / 'seeded.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    with open(out_dir / 'ground_truth.json', 'w') as f:
        json.dump(gt, f, indent=2)
    bad_count = sum(1 for v in gt.values() if v != 'clean')
    print(f"Wrote {len(rows)} rows ({bad_count} seeded violations) → eval/seeded.csv + eval/ground_truth.json")
