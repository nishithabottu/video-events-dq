import re
from datetime import datetime, timedelta, timezone
from rules.registry import register_rule, REGISTRY
from loader import load_events

VALID_EVENT_TYPES = {'playback_start', 'playback_end', 'buffer_start', 'buffer_end', 'error'}
VALID_PLATFORMS = {'roku', 'stva', 'specguide', 'odn', 'tve'}
VALID_ERROR_CODES = {f'E{i:03d}' for i in range(1, 11)}    # ← E001..E010
FIRMWARE_REGEX = re.compile(r'^\d+\.\d+\.\d+$')            # ← X.Y.Z format
THIRTY_DAYS_AGO = datetime.now(timezone.utc) - timedelta(days=30)

# ─────────── UNIQUENESS ───────────

@register_rule(
    id="UNIQ_001",
    category="Uniqueness",
    severity="critical",
    description="event_id must be unique across the dataset",
    downstream_impact="Duplicates double-count events in every aggregation and bias anomaly baselines"
)
def event_id_duplicates(df):
    dupes = df[df['event_id'].duplicated(keep=False)]    # ← Flag every duplicate row
    return dupes.index.tolist()                          # ← Return offending row indices

# ─────────── NULLABILITY ───────────

@register_rule(
    id="NULL_001",
    category="Nullability",
    severity="critical",
    description="content_id must not be null on playback events",
    downstream_impact="Null content_id breaks per-title rollups in the QoE Scorecard dashboard"
)
def content_id_null_on_playback(df):
    mask = df['content_id'].isna() & df['event_type'].isin(['playback_start', 'playback_end'])
    return df[mask].index.tolist()

@register_rule(
    id="NULL_002",
    category="Nullability",
    severity="critical",
    description="device_id must never be null",
    downstream_impact="Null device_id corrupts device-cohort analyses and platform reliability metrics"
)
def device_id_null(df):
    return df[df['device_id'].isna()].index.tolist()

# ─────────── DOMAIN / ENUM ───────────

@register_rule(
    id="ENUM_001",
    category="Domain/Enum",
    severity="warning",
    description="error_code must be in E001–E010 when populated",
    downstream_impact="Invalid codes corrupt error-rate metrics and trigger false anomaly alerts"
)
def error_code_invalid(df):
    mask = df['error_code'].notna() & ~df['error_code'].isin(VALID_ERROR_CODES)
    return df[mask].index.tolist()

# ─────────── RANGE / FORMAT ───────────

@register_rule(
    id="RANGE_001",
    category="Range/Format",
    severity="critical",
    description="duration_ms must be >= 0 when non-null",
    downstream_impact="Negative durations corrupt avg-session-duration on the leadership Tableau scorecard"
)
def duration_ms_negative(df):
    mask = df['duration_ms'].notna() & (df['duration_ms'] < 0)
    return df[mask].index.tolist()

@register_rule(
    id="RANGE_002",
    category="Range/Format",
    severity="warning",
    description="duration_ms must be null for playback_start and buffer_start events",
    downstream_impact="Spurious durations on start events inflate avg-session-duration metrics"
)
def duration_ms_should_be_null_on_start(df):
    mask = df['duration_ms'].notna() & df['event_type'].isin(['playback_start', 'buffer_start'])
    return df[mask].index.tolist()

@register_rule(
    id="RANGE_003",
    category="Range/Format",
    severity="warning",
    description="timestamp must be within the last 30 days",
    downstream_impact="Out-of-window events skew 7-day rolling baselines used by anomaly alerts"
)
def timestamp_outside_window(df):
    mask = df['timestamp'] < THIRTY_DAYS_AGO
    return df[mask].index.tolist()

@register_rule(
    id="FMT_001",
    category="Range/Format",
    severity="info",
    description="firmware_version must match X.Y.Z format",
    downstream_impact="Malformed firmware breaks device-cohort analyses in fleet health reports"
)
def firmware_version_format(df):
    def bad(v):
        if v is None or (isinstance(v, float) and v != v):  # ← NaN check
            return True
        return not FIRMWARE_REGEX.match(str(v))
    mask = df['firmware_version'].apply(bad)
    return df[mask].index.tolist()

# ─────────── SCHEMA / TYPE ───────────

@register_rule(
    id="SCHEMA_001",
    category="Schema/Type",
    severity="critical",
    description="timestamp must parse as valid ISO 8601",
    downstream_impact="Unparseable timestamps drop rows from every time-windowed aggregation"
)
def timestamp_unparseable(df):
    return df[df['timestamp'].isna()].index.tolist()

# ─────────── DOMAIN / ENUM (more) ───────────

@register_rule(
    id="ENUM_002",
    category="Domain/Enum",
    severity="critical",
    description="event_type must be one of the five defined values",
    downstream_impact="Invalid event_types corrupt every metric grouped by event type"
)
def event_type_invalid(df):
    return df[~df['event_type'].isin(VALID_EVENT_TYPES)].index.tolist()

@register_rule(
    id="ENUM_003",
    category="Domain/Enum",
    severity="critical",
    description="platform must be one of the five defined values",
    downstream_impact="Invalid platforms break platform-partitioned Tableau dashboards directly"
)
def platform_invalid(df):
    return df[~df['platform'].isin(VALID_PLATFORMS)].index.tolist()

# ─────────── NULLABILITY (more) ───────────

@register_rule(
    id="NULL_003",
    category="Nullability",
    severity="warning",
    description="error_code must be null when event_type is not 'error'",
    downstream_impact="Spurious error codes inflate error-rate metrics and trigger false alerts"
)
def error_code_on_non_error(df):
    mask = df['error_code'].notna() & (df['event_type'] != 'error')
    return df[mask].index.tolist()

@register_rule(
    id="NULL_004",
    category="Nullability",
    severity="critical",
    description="error_code must be non-null when event_type is 'error'",
    downstream_impact="Missing error codes prevent error categorization in Platform Reliability dashboard"
)
def error_code_missing_on_error(df):
    mask = df['error_code'].isna() & (df['event_type'] == 'error')
    return df[mask].index.tolist()

# ─────────── REFERENTIAL / SESSION INTEGRITY ───────────

@register_rule(
    id="REF_001",
    category="Referential/Session",
    severity="warning",
    description="every session with a playback_start must have a playback_end",
    downstream_impact="Unclosed sessions corrupt avg-session-duration on the Session Duration Trends dashboard"
)
def session_missing_playback_end(df):
    sess_events = df.groupby('session_id')['event_type'].apply(set)
    bad_sessions = sess_events[sess_events.apply(lambda s: 'playback_start' in s and 'playback_end' not in s)].index
    return df[df['session_id'].isin(bad_sessions) & (df['event_type'] == 'playback_start')].index.tolist()

@register_rule(
    id="REF_002",
    category="Referential/Session",
    severity="warning",
    description="every session with a playback_end must have a playback_start",
    downstream_impact="Orphan end events corrupt session-completion metrics"
)
def session_missing_playback_start(df):
    sess_events = df.groupby('session_id')['event_type'].apply(set)
    bad_sessions = sess_events[sess_events.apply(lambda s: 'playback_end' in s and 'playback_start' not in s)].index
    return df[df['session_id'].isin(bad_sessions) & (df['event_type'] == 'playback_end')].index.tolist()

@register_rule(
    id="REF_003",
    category="Referential/Session",
    severity="warning",
    description="every buffer_start must have a matching buffer_end in the same session",
    downstream_impact="Unclosed buffer events corrupt buffer-ratio metrics on the QoE Scorecard"
)
def session_missing_buffer_end(df):
    sess_events = df.groupby('session_id')['event_type'].apply(set)
    bad_sessions = sess_events[sess_events.apply(lambda s: 'buffer_start' in s and 'buffer_end' not in s)].index
    return df[df['session_id'].isin(bad_sessions) & (df['event_type'] == 'buffer_start')].index.tolist()

if __name__ == '__main__':
    df = load_events('video_events_sample.csv')
    print(f"Registry now has {len(REGISTRY)} rule(s)")
    for rule in REGISTRY:
        bad_rows = rule.check(df)
        print(f"  {rule.id} ({rule.severity}): found {len(bad_rows)} violations")
