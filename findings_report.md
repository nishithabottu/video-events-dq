# Data Quality Report — Video Events

_Generated 2026-05-26T11:14:15.866610+00:00_

## Executive Summary

Ran **16 rules** against the dataset. **12 rules found violations**, 4 passed clean.

**Top 3 issues by downstream blast radius:**

- **UNIQ_001** (critical, 88 rows) — duplicate event_ids double-count every aggregation and bias the 7-day rolling baseline behind the >15% anomaly alert.
- **NULL_001** (critical, 27 rows) — null content_id on playback drops rows from the QoE Scorecard's per-title rollup; the content team cannot see which titles are buffering.
- **REF_001 + REF_002** (warning, 173 rows combined) — unpaired playback_start/playback_end events corrupt the average-session-duration metric on the Session Duration Trends dashboard.

## What this means for your dashboards

Today's sample contains issues that touch every downstream surface the Video Insights team owns. The **Session Duration Trends** dashboard pulls from `session_metrics_daily`, which joins on event_id and pairs playback_start/playback_end — the duplicate event_ids (UNIQ_001) and the orphaned start/end events (REF_001, REF_002) both bias average session duration in different directions. The **QoE Scorecard** rolls up buffer ratio per title; null content_ids (NULL_001) drop rows from that rollup entirely, and unclosed buffer events (REF_003) inflate buffering time. The **Platform Reliability** report depends on a valid device_id and a documented error_code; nulls (NULL_002) and out-of-catalog codes (ENUM_001) under-count platform incidents. Finally, the **>15% anomaly alert** is keyed off a 7-day rolling baseline of these same aggregates — duplicates and out-of-window timestamps (RANGE_003) can either fire the alert with no real incident behind it or mask one that's actually happening. None of the corrupted metrics will surface as obviously wrong; analysts will chase phantom signals until the rules fail at ingest.

## Findings

### UNIQ_001 — CRITICAL — 88 violations

**Rule:** event_id must be unique across the dataset  
**Category:** Uniqueness  
**Downstream impact:** Duplicates double-count events in every aggregation and bias anomaly baselines

**Plain-English explanation:**  
> 88 event_ids appear more than once. Because every aggregation joins on event_id, these duplicates inflate play counts and bias the 7-day rolling baseline used by the >15% anomaly alert — analysts will chase phantom spikes. Action: dedupe at ingest before session_metrics_daily is built.

**Suggested owner:** Video Insights ingest team  
**Confidence:** 0.85  
**Sample event_ids:** `a3a65b03-93ce-414f-a817-ac9e9f4cebe2, b97aa32c-f4d7-4e13-adaf-4fe2919d9f6a, b97aa32c-f4d7-4e13-adaf-4fe2919d9f6a, 856e356e-84d1-4c2e-a7f9-af6ce2264338, e831fae4-51a0-469e-a7c6-23e3d929ca75`

### NULL_001 — CRITICAL — 27 violations

**Rule:** content_id must not be null on playback events  
**Category:** Nullability  
**Downstream impact:** Null content_id breaks per-title rollups in the QoE Scorecard dashboard

**Plain-English explanation:**  
> 27 playback events are missing content_id. The QoE Scorecard groups buffer ratio and play counts by title — these rows fall out of the rollup entirely, so the content team cannot see which titles are buffering. Action: make content_id NOT NULL on playback_start and playback_end at the schema level.

**Suggested owner:** STB / mobile client teams (source of the playback event)  
**Confidence:** 0.85  
**Sample event_ids:** `541785d7-43c9-4028-bc8f-7b515411d14b, 088fdb07-f7d1-4e9f-88ac-04c9c771e9e5, bb586c86-b2a1-42a2-91d4-771e2ce1147b, fa84b507-71fd-42ca-adfd-0e4e5ef8e478, 77f29c19-67db-455c-84c4-ead61459fc8b`

### RANGE_001 — CRITICAL — 20 violations

**Rule:** duration_ms must be >= 0 when non-null  
**Category:** Range/Format  
**Downstream impact:** Negative durations corrupt avg-session-duration on the leadership Tableau scorecard

**Plain-English explanation:**  
> 20 events have a negative duration_ms. Negative durations pull the average-session-duration metric below truth on the leadership Tableau scorecard. Action: clamp at the source or drop these rows in the daily rollup.

**Suggested owner:** STB / mobile client teams  
**Confidence:** 0.85  
**Sample event_ids:** `6d3c3973-9e7d-4069-89a3-fcbc8bb33d3f, de6dad98-c148-4a49-9795-0043fc067f93, 033de5e0-6871-4348-af06-7371a92e2027, e69a470b-a30f-43f1-afa6-d23dcdfe10d5, c6bf982e-fd5c-475f-955c-c3ecac6331b6`

### NULL_002 — CRITICAL — 5 violations

**Rule:** device_id must never be null  
**Category:** Nullability  
**Downstream impact:** Null device_id corrupts device-cohort analyses and platform reliability metrics

**Plain-English explanation:**  
> 5 events are missing device_id. Device-cohort analyses and the Platform Reliability report cannot attribute these events to a fleet, so platform-level error rates are under-counted. Action: reject events without device_id at the collector.

**Suggested owner:** STB / mobile client teams  
**Confidence:** 0.85  
**Sample event_ids:** `00b45cde-e17c-4a49-ba6b-e4295e72ca5a, 90184e6b-3086-4b9e-a710-2f4207109d77, f62040e6-138b-4e72-9b03-d6ce06547657, 54156e66-73d6-4e18-80b7-4c9c090d7e8b, e1bcb4a6-cf34-4f2b-961e-d0bc02d4d9ee`

### RANGE_003 — WARNING — 591 violations

**Rule:** timestamp must be within the last 30 days  
**Category:** Range/Format  
**Downstream impact:** Out-of-window events skew 7-day rolling baselines used by anomaly alerts

**Plain-English explanation:**  
> 591 events fall outside the trailing-30-day window expected by the 7-day rolling baseline. Out-of-window rows skew the baseline and can either mask real anomalies or trigger false ones on the >15% alert. Action: filter on event timestamp at the ingest boundary.

**Suggested owner:** Video Insights ingest team  
**Confidence:** 0.85  
**Sample event_ids:** `9f3342e6-e410-4df5-8b32-d6d589a3c3b2, a8075482-3ffd-4d3e-8ed8-b37afd9f3676, a10e2b8f-12db-4a03-b982-8fb477f081f6, c1fdc98d-cf63-4d91-b5e8-769c9128373f, 5e43011e-a8c7-4eaa-acc2-d093b3fe10cf`

### REF_002 — WARNING — 107 violations

**Rule:** every session with a playback_end must have a playback_start  
**Category:** Referential/Session  
**Downstream impact:** Orphan end events corrupt session-completion metrics

**Plain-English explanation:**  
> 107 sessions have an orphan playback_end with no playback_start. These show up as completed sessions of unknown length on the Session Duration Trends dashboard and corrupt the session-completion metric. Action: confirm whether starts are being dropped at the collector, then either backfill or filter orphans.

**Suggested owner:** Video Insights ingest team  
**Confidence:** 0.85  
**Sample event_ids:** `c1fdc98d-cf63-4d91-b5e8-769c9128373f, 8dbce9fd-4b06-4576-b0b0-c7b2f4a6f9f8, d1951d41-7de9-4929-a7f7-2cf717faa398, c9c75f23-82d4-4fd2-aa70-d23e55db6bb8, 01f18fcc-2bf8-4ef7-9997-95feba6e8d73`

### REF_003 — WARNING — 69 violations

**Rule:** every buffer_start must have a matching buffer_end in the same session  
**Category:** Referential/Session  
**Downstream impact:** Unclosed buffer events corrupt buffer-ratio metrics on the QoE Scorecard

**Plain-English explanation:**  
> 69 buffer_start events have no matching buffer_end in the same session. The QoE Scorecard's buffer-ratio metric depends on paired start/end events; unclosed buffers inflate buffering time. Action: emit a buffer_end on session teardown if one was missed.

**Suggested owner:** STB / mobile client teams  
**Confidence:** 0.85  
**Sample event_ids:** `a3a65b03-93ce-414f-a817-ac9e9f4cebe2, 0a27448a-ce10-4383-9720-79bccd517865, 856e356e-84d1-4c2e-a7f9-af6ce2264338, 0dc7a9ac-60e0-4736-a61f-13b650f8c905, 20481987-14f9-4943-872c-4ddb72764ba5`

### REF_001 — WARNING — 66 violations

**Rule:** every session with a playback_start must have a playback_end  
**Category:** Referential/Session  
**Downstream impact:** Unclosed sessions corrupt avg-session-duration on the Session Duration Trends dashboard

**Plain-English explanation:**  
> 66 sessions have a playback_start with no matching playback_end. Without a paired end event, the Session Duration Trends dashboard cannot compute session length for these sessions, so average-session-duration is computed on a biased subset. Action: investigate client-side drop/crash paths and add an end-of-session sentinel.

**Suggested owner:** STB / mobile client teams  
**Confidence:** 0.85  
**Sample event_ids:** `1a7fc18b-69bb-4fd6-bf9c-d92c0a9c1d13, 5ed3966f-9669-4ec9-ba82-0a5285aed851, 805573fd-d77b-4a72-b78d-5e9569c85ed4, 2440df2f-bfd2-443d-97f7-28fe5cac54b6, 87bcc85e-32ae-4e86-91a7-3ce7d3cbffb8`

### NULL_003 — WARNING — 15 violations

**Rule:** error_code must be null when event_type is not 'error'  
**Category:** Nullability  
**Downstream impact:** Spurious error codes inflate error-rate metrics and trigger false alerts

**Plain-English explanation:**  
> 15 non-error events carry an error_code. These spurious codes inflate the platform error rate and can trip the >15% anomaly alert with no real incident behind it. Action: clear error_code on non-error events at the transform step.

**Suggested owner:** Video Insights ingest team  
**Confidence:** 0.85  
**Sample event_ids:** `30a9de9c-9257-470d-9f7f-c48f8cd5426b, 60fb28ab-17ac-46c1-8556-57c0519864cf, de6dad98-c148-4a49-9795-0043fc067f93, 033de5e0-6871-4348-af06-7371a92e2027, f9643434-ddb3-4d71-b0dd-66e4fada138a`

### RANGE_002 — WARNING — 9 violations

**Rule:** duration_ms must be null for playback_start and buffer_start events  
**Category:** Range/Format  
**Downstream impact:** Spurious durations on start events inflate avg-session-duration metrics

**Plain-English explanation:**  
> 9 playback_start or buffer_start events carry a non-null duration. Start events should have no duration; including them double-counts time in the average-session-duration metric. Action: null duration_ms on start events in the transform.

**Suggested owner:** Video Insights ingest team  
**Confidence:** 0.85  
**Sample event_ids:** `bb586c86-b2a1-42a2-91d4-771e2ce1147b, 30a9de9c-9257-470d-9f7f-c48f8cd5426b, 29d28a22-1247-4aeb-9f0f-9e4d3b999a82, ff90ad4d-55fc-4057-9aca-e00ce0160d09, ad355f6d-eaa5-4958-86e7-da1677aa03cf`

### ENUM_001 — WARNING — 8 violations

**Rule:** error_code must be in E001–E010 when populated  
**Category:** Domain/Enum  
**Downstream impact:** Invalid codes corrupt error-rate metrics and trigger false anomaly alerts

**Plain-English explanation:**  
> 8 rows carry an error_code outside the documented E001–E010 set. These codes bucket into 'unknown' on the Platform Reliability dashboard, so root-cause counts under-report. Action: extend the catalog or fix the emitter, then backfill.

**Suggested owner:** Platform Reliability / device firmware team  
**Confidence:** 0.85  
**Sample event_ids:** `df6972b5-d552-4935-8d33-92eafb0f89a5, 42c071e1-d477-4f0a-929c-75dd0a1edede, 866ae35e-8bc9-4963-8bbc-47234f53eb5f, 959f5021-cccf-44dd-a818-c7aa87847606, 56bed18f-ed68-4fd0-8ff3-544598731c73`

### FMT_001 — INFO — 6 violations

**Rule:** firmware_version must match X.Y.Z format  
**Category:** Range/Format  
**Downstream impact:** Malformed firmware breaks device-cohort analyses in fleet health reports

**Plain-English explanation:**  
> 6 rows have a firmware_version that does not match the documented X.Y.Z pattern. Device-cohort analyses in fleet-health reports cannot group these rows by version, so firmware-regressing rollouts are harder to detect. Action: normalize firmware strings at the collector.

**Suggested owner:** Device firmware team  
**Confidence:** 0.85  
**Sample event_ids:** `9784c6fd-7b1a-4948-a350-10e2276bacc8, db3dc9f1-d0a1-4518-8d7e-efc3c3e03200, 15e0953b-1934-4fe7-ae0d-b33a7803390e, b3a3bb5a-5d75-45b8-b52a-b541cee893ef, a5ad0983-8206-4e5e-a8af-ba23f34330fd`

## Passed Checks

- **SCHEMA_001** (Schema/Type) — timestamp must parse as valid ISO 8601
- **ENUM_002** (Domain/Enum) — event_type must be one of the five defined values
- **ENUM_003** (Domain/Enum) — platform must be one of the five defined values
- **NULL_004** (Nullability) — error_code must be non-null when event_type is 'error'