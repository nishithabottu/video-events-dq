import pandas as pd
from rules.registry import REGISTRY
import rules.checks                                       # ← Triggers registration

RULES = {r.id: r for r in REGISTRY}                       # ← Easy lookup by id

CLEAN = {
    'event_id': 'evt_1', 'event_type': 'playback_end', 'session_id': 'sess_1',
    'platform': 'roku', 'content_id': 'content_0001',
    'timestamp': '2026-05-15T12:00:00Z', 'duration_ms': '120000',
    'device_id': 'device_abc', 'firmware_version': '12.1.3', 'error_code': ''
}

def make_df(rows):
    df = pd.DataFrame(rows)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    df['duration_ms'] = pd.to_numeric(df['duration_ms'], errors='coerce').astype('Int64')
    return df

# ─── UNIQ_001 — duplicate event_id ───
def test_uniq_001_fires():
    df = make_df([{**CLEAN, 'event_id': 'dup'}, {**CLEAN, 'event_id': 'dup', 'session_id': 's2'}])
    assert len(RULES['UNIQ_001'].check(df)) == 2

def test_uniq_001_clean():
    df = make_df([CLEAN, {**CLEAN, 'event_id': 'evt_2'}])
    assert RULES['UNIQ_001'].check(df) == []

# ─── NULL_001 — content_id null on playback ───
def test_null_001_fires():
    df = make_df([{**CLEAN, 'event_type': 'playback_start', 'duration_ms': '', 'content_id': None}])
    assert len(RULES['NULL_001'].check(df)) == 1

def test_null_001_clean():
    assert RULES['NULL_001'].check(make_df([CLEAN])) == []

# ─── ENUM_001 — invalid error_code ───
def test_enum_001_fires():
    df = make_df([{**CLEAN, 'event_type': 'error', 'duration_ms': '500', 'error_code': 'UNKNOWN'}])
    assert len(RULES['ENUM_001'].check(df)) == 1

def test_enum_001_clean():
    df = make_df([{**CLEAN, 'event_type': 'error', 'duration_ms': '500', 'error_code': 'E005'}])
    assert RULES['ENUM_001'].check(df) == []

# ─── RANGE_001 — negative duration_ms ───
def test_range_001_fires():
    df = make_df([{**CLEAN, 'duration_ms': '-100'}])
    assert len(RULES['RANGE_001'].check(df)) == 1

def test_range_001_clean():
    assert RULES['RANGE_001'].check(make_df([CLEAN])) == []

# ─── FMT_001 — bad firmware format ───
def test_fmt_001_fires():
    df = make_df([{**CLEAN, 'firmware_version': 'v12.1'}])
    assert len(RULES['FMT_001'].check(df)) == 1

def test_fmt_001_clean():
    assert RULES['FMT_001'].check(make_df([CLEAN])) == []

# ─── REF_001 — playback_start with no playback_end ───
def test_ref_001_fires():
    df = make_df([{**CLEAN, 'event_type': 'playback_start', 'duration_ms': '', 'session_id': 'lonely'}])
    assert len(RULES['REF_001'].check(df)) == 1

def test_ref_001_clean():
    # Paired start + end in same session — should NOT fire
    df = make_df([
        {**CLEAN, 'event_type': 'playback_start', 'duration_ms': '', 'session_id': 'paired'},
        {**CLEAN, 'event_type': 'playback_end', 'event_id': 'evt_2', 'session_id': 'paired'}
    ])
    assert RULES['REF_001'].check(df) == []
