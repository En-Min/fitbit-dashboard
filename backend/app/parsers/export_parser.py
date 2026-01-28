"""
Parser for Google Takeout / Fitbit bulk export ZIP files.

Supports two directory layouts:
  - Google Takeout:   Takeout/Fitbit/Global Export Data/...
  - Old Fitbit export: MyFitbitData/...

Each data type is handled by a dedicated internal function. Records are
inserted in batches (default 1000) and duplicates are silently skipped
using unique-constraint checks before insert.
"""

import csv
import io
import json
import logging
import os
import zipfile
from datetime import datetime, date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    HeartRateIntraday,
    HeartRateDaily,
    SleepLog,
    SleepStage,
    SpO2Daily,
    SpO2Intraday,
    HRVDaily,
    HRVIntraday,
    SkinTemperature,
    StressScore,
    ReadinessScore,
    ActivityDaily,
    ActivityIntraday,
    Exercise,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_fitbit_timestamp(raw: str) -> datetime:
    """Parse the 'MM/DD/YY HH:MM:SS' format used in heart-rate JSON exports."""
    return datetime.strptime(raw, "%m/%d/%y %H:%M:%S")


def _parse_iso_timestamp(raw: str) -> datetime:
    """Parse ISO-8601-ish timestamps that Fitbit uses in most JSON exports.

    Handles formats like:
      2024-01-15T08:30:00.000
      2024-01-15T08:30:00
      2024-01-15 08:30:00
      01/15/24 08:30:00
    """
    raw = raw.strip()
    # Try MM/DD/YY first (heart-rate style)
    for fmt in (
        "%m/%d/%y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse timestamp: {raw!r}")


def _parse_date_from_string(raw: str) -> date:
    """Parse a date string into a date object, trying common formats."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {raw!r}")


def _safe_int(value: Any, default: int | None = None) -> int | None:
    """Safely convert a value to int, returning *default* on failure."""
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    """Safely convert a value to float, returning *default* on failure."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _flush_batch(db: Session, batch: list) -> int:
    """Add a batch of ORM objects to the session, commit, and return the count.

    Duplicates are handled by attempting individual inserts on flush failure.
    """
    if not batch:
        return 0
    count = 0
    for obj in batch:
        db.add(obj)
        count += 1
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Fall back to one-at-a-time to skip duplicates
        count = 0
        for obj in batch:
            try:
                db.add(obj)
                db.commit()
                count += 1
            except Exception:
                db.rollback()
    batch.clear()
    return count


def _find_base_path(zf: zipfile.ZipFile) -> str:
    """Detect whether the ZIP uses the Google Takeout or old Fitbit layout.

    Returns the prefix path to the Fitbit data directory (with trailing slash).
    """
    names = zf.namelist()
    for name in names:
        # Google Takeout layout
        if "Takeout/Fitbit/" in name:
            idx = name.index("Takeout/Fitbit/")
            return name[: idx] + "Takeout/Fitbit/"
        # Old Fitbit export layout
        if "MyFitbitData/" in name:
            idx = name.index("MyFitbitData/")
            return name[: idx] + "MyFitbitData/"
    # Fallback: try root-level files
    return ""


def _list_files(zf: zipfile.ZipFile, base: str, subdir: str, ext: str) -> list[str]:
    """Return ZIP member names matching base/subdir/**/*.ext (case-insensitive ext)."""
    prefix = base + subdir
    result = []
    for name in zf.namelist():
        if name.startswith(prefix) and name.lower().endswith(ext.lower()):
            result.append(name)
    return sorted(result)


def _read_json(zf: zipfile.ZipFile, path: str) -> Any:
    """Read and parse a JSON file from inside the ZIP."""
    with zf.open(path) as f:
        raw = f.read().decode("utf-8-sig")  # handle BOM
        return json.loads(raw)


def _read_csv_rows(zf: zipfile.ZipFile, path: str) -> list[dict]:
    """Read a CSV file from inside the ZIP and return rows as dicts."""
    with zf.open(path) as f:
        text = f.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)


# ---------------------------------------------------------------------------
# Data-type parsers
# ---------------------------------------------------------------------------


def _parse_heart_rate_json(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse heart_rate-YYYY-MM-DD.json files into HeartRateIntraday."""
    total = 0
    batch: list[HeartRateIntraday] = []

    for path in files:
        try:
            data = _read_json(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        if not isinstance(data, list):
            continue

        for entry in data:
            try:
                ts = _parse_iso_timestamp(entry["dateTime"])
                value = entry.get("value", {})
                bpm = _safe_int(value.get("bpm") if isinstance(value, dict) else value)
                confidence = _safe_int(
                    value.get("confidence") if isinstance(value, dict) else None
                )
                if bpm is None:
                    continue

                batch.append(
                    HeartRateIntraday(timestamp=ts, bpm=bpm, confidence=confidence)
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("Heart rate entry error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_sleep_json(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse sleep-YYYY-MM-DD.json files into SleepLog and SleepStage."""
    total = 0

    for path in files:
        try:
            data = _read_json(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        if not isinstance(data, list):
            continue

        for entry in data:
            try:
                log_id = str(entry.get("logId", ""))
                if not log_id:
                    continue

                # Check for duplicate
                existing = (
                    db.query(SleepLog).filter(SleepLog.log_id == log_id).first()
                )
                if existing:
                    continue

                start_time = _parse_iso_timestamp(entry["startTime"])
                end_time = _parse_iso_timestamp(entry["endTime"])
                sleep_date = start_time.date()

                sleep_log = SleepLog(
                    log_id=log_id,
                    date=sleep_date,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=_safe_int(entry.get("duration")),
                    efficiency=_safe_int(entry.get("efficiency")),
                    minutes_asleep=_safe_int(entry.get("minutesAsleep")),
                    minutes_awake=_safe_int(entry.get("minutesAwake")),
                    time_in_bed=_safe_int(entry.get("timeInBed")),
                    type=entry.get("type"),
                )

                # Extract stage summary from "levels"
                levels = entry.get("levels", {})
                summary = levels.get("summary", {})
                if summary:
                    sleep_log.deep_sleep_minutes = _safe_int(
                        summary.get("deep", {}).get("minutes")
                    )
                    sleep_log.rem_sleep_minutes = _safe_int(
                        summary.get("rem", {}).get("minutes")
                    )
                    sleep_log.light_sleep_minutes = _safe_int(
                        summary.get("light", {}).get("minutes")
                    )

                db.add(sleep_log)
                db.flush()  # get the auto-generated id
                total += 1

                # Parse individual stage data
                stage_data = levels.get("data", [])
                short_data = levels.get("shortData", [])
                all_stages = stage_data + short_data

                stage_batch: list[SleepStage] = []
                for stage_entry in all_stages:
                    try:
                        stage_ts = _parse_iso_timestamp(stage_entry["dateTime"])
                        stage_batch.append(
                            SleepStage(
                                sleep_log_id=sleep_log.id,
                                timestamp=stage_ts,
                                stage=stage_entry.get("level", "unknown"),
                                duration_seconds=_safe_int(
                                    stage_entry.get("seconds")
                                ),
                            )
                        )
                        if len(stage_batch) >= BATCH_SIZE:
                            _flush_batch(db, stage_batch)
                    except Exception as exc:
                        logger.debug("Sleep stage entry error: %s", exc)
                        continue

                _flush_batch(db, stage_batch)
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning("Sleep log entry error in %s: %s", path, exc)
                continue

    return total


def _parse_activity_json(
    zf: zipfile.ZipFile,
    files: list[str],
    metric: str,
    db: Session,
) -> int:
    """Parse steps/calories/distance/altitude JSON into ActivityIntraday.

    Each file is an array of {dateTime, value} entries.
    """
    total = 0
    batch: list[ActivityIntraday] = []

    for path in files:
        try:
            data = _read_json(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        if not isinstance(data, list):
            continue

        for entry in data:
            try:
                ts = _parse_iso_timestamp(entry["dateTime"])
                value = _safe_float(entry.get("value"))
                if value is None:
                    continue

                batch.append(
                    ActivityIntraday(timestamp=ts, metric=metric, value=value)
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("Activity %s entry error: %s", metric, exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_exercise_json(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse exercise-YYYY-MM-DD.json into Exercise table."""
    total = 0

    for path in files:
        try:
            data = _read_json(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        if not isinstance(data, list):
            continue

        for entry in data:
            try:
                log_id = str(entry.get("logId", ""))
                if not log_id:
                    continue

                existing = (
                    db.query(Exercise).filter(Exercise.log_id == log_id).first()
                )
                if existing:
                    continue

                start_time = _parse_iso_timestamp(entry["startTime"])
                exercise_date = start_time.date()

                end_time = None
                if entry.get("endTime"):
                    end_time = _parse_iso_timestamp(entry["endTime"])
                elif entry.get("activeDuration"):
                    duration_ms = _safe_int(entry["activeDuration"])
                    if duration_ms is not None:
                        end_time = start_time + timedelta(milliseconds=duration_ms)

                exercise = Exercise(
                    log_id=log_id,
                    date=exercise_date,
                    start_time=start_time,
                    end_time=end_time,
                    activity_name=entry.get("activityName", "Unknown"),
                    duration_ms=_safe_int(entry.get("activeDuration") or entry.get("duration")),
                    calories=_safe_int(entry.get("calories")),
                    average_heart_rate=_safe_int(entry.get("averageHeartRate")),
                    steps=_safe_int(entry.get("steps")),
                    distance_km=_safe_float(entry.get("distance")),
                )

                db.add(exercise)
                db.commit()
                total += 1
            except Exception as exc:
                db.rollback()
                logger.warning("Exercise entry error in %s: %s", path, exc)
                continue

    return total


def _parse_hrv_daily_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Daily Heart Rate Variability Summary CSV files."""
    total = 0
    batch: list[HRVDaily] = []

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                # Column names vary; try common variants
                date_str = (
                    row.get("timestamp")
                    or row.get("date")
                    or row.get("Date")
                    or row.get("Timestamp")
                    or ""
                )
                if not date_str:
                    continue

                record_date = _parse_date_from_string(date_str.split("T")[0].split(" ")[0])

                daily_rmssd = _safe_float(
                    row.get("rmssd")
                    or row.get("Daily RMSSD")
                    or row.get("daily_rmssd")
                )
                deep_rmssd = _safe_float(
                    row.get("deep_rmssd")
                    or row.get("Deep RMSSD")
                    or row.get("nremRmssd")
                )

                if daily_rmssd is None and deep_rmssd is None:
                    continue

                batch.append(
                    HRVDaily(
                        date=record_date,
                        daily_rmssd=daily_rmssd,
                        deep_rmssd=deep_rmssd,
                    )
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("HRV daily row error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_hrv_details_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Heart Rate Variability Details CSV files into HRVIntraday."""
    total = 0
    batch: list[HRVIntraday] = []

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                ts_str = (
                    row.get("timestamp")
                    or row.get("Timestamp")
                    or row.get("dateTime")
                    or ""
                )
                if not ts_str:
                    continue

                ts = _parse_iso_timestamp(ts_str)
                rmssd = _safe_float(
                    row.get("rmssd") or row.get("RMSSD") or row.get("hrv")
                )
                if rmssd is None:
                    continue

                batch.append(
                    HRVIntraday(
                        timestamp=ts,
                        rmssd=rmssd,
                        coverage=_safe_float(
                            row.get("coverage") or row.get("Coverage")
                        ),
                        hf=_safe_float(row.get("hf") or row.get("HF")),
                        lf=_safe_float(row.get("lf") or row.get("LF")),
                    )
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("HRV detail row error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_spo2_daily_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Daily SpO2 CSV files."""
    total = 0
    batch: list[SpO2Daily] = []

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                date_str = (
                    row.get("timestamp")
                    or row.get("date")
                    or row.get("Date")
                    or row.get("Timestamp")
                    or ""
                )
                if not date_str:
                    continue

                record_date = _parse_date_from_string(date_str.split("T")[0].split(" ")[0])

                avg_spo2 = _safe_float(
                    row.get("avg_spo2")
                    or row.get("Average SpO2")
                    or row.get("Avg Value")
                    or row.get("avgValue")
                )
                min_spo2 = _safe_float(
                    row.get("min_spo2")
                    or row.get("Min SpO2")
                    or row.get("Min Value")
                    or row.get("minValue")
                )
                max_spo2 = _safe_float(
                    row.get("max_spo2")
                    or row.get("Max SpO2")
                    or row.get("Max Value")
                    or row.get("maxValue")
                )

                if avg_spo2 is None and min_spo2 is None and max_spo2 is None:
                    continue

                batch.append(
                    SpO2Daily(
                        date=record_date,
                        avg_spo2=avg_spo2,
                        min_spo2=min_spo2,
                        max_spo2=max_spo2,
                    )
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("SpO2 daily row error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_spo2_intraday_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Minute SpO2 CSV files into SpO2Intraday."""
    total = 0
    batch: list[SpO2Intraday] = []

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                ts_str = (
                    row.get("timestamp")
                    or row.get("Timestamp")
                    or row.get("dateTime")
                    or ""
                )
                if not ts_str:
                    continue

                ts = _parse_iso_timestamp(ts_str)
                spo2 = _safe_float(
                    row.get("value") or row.get("Value") or row.get("spo2")
                )
                if spo2 is None:
                    continue

                batch.append(SpO2Intraday(timestamp=ts, spo2=spo2))

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("SpO2 intraday row error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_temperature_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Device Temperature CSV files."""
    total = 0
    batch: list[SkinTemperature] = []

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                date_str = (
                    row.get("date")
                    or row.get("Date")
                    or row.get("timestamp")
                    or row.get("Timestamp")
                    or row.get("sleep_start")
                    or ""
                )
                if not date_str:
                    continue

                record_date = _parse_date_from_string(date_str.split("T")[0].split(" ")[0])

                temp = _safe_float(
                    row.get("relative_temp")
                    or row.get("Temperature")
                    or row.get("temperature")
                    or row.get("nightly_temp")
                    or row.get("Nightly Temperature")
                )
                if temp is None:
                    continue

                batch.append(
                    SkinTemperature(date=record_date, relative_temp=temp)
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("Temperature row error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_stress_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Stress Score CSV files."""
    total = 0
    batch: list[StressScore] = []

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                date_str = (
                    row.get("DATE")
                    or row.get("date")
                    or row.get("Date")
                    or row.get("timestamp")
                    or ""
                )
                if not date_str:
                    continue

                record_date = _parse_date_from_string(date_str.split("T")[0].split(" ")[0])

                score = _safe_int(
                    row.get("STRESS_SCORE")
                    or row.get("stress_score")
                    or row.get("Stress Score")
                    or row.get("stressManagementScore")
                )
                if score is None:
                    continue

                batch.append(
                    StressScore(
                        date=record_date,
                        stress_score=score,
                        exertion_score=_safe_int(
                            row.get("EXERTION_SCORE")
                            or row.get("exertion_score")
                            or row.get("Exertion Score")
                        ),
                        responsiveness_score=_safe_int(
                            row.get("RESPONSIVENESS_SCORE")
                            or row.get("responsiveness_score")
                            or row.get("Responsiveness Score")
                        ),
                        sleep_score_component=_safe_int(
                            row.get("SLEEP_SCORE")
                            or row.get("sleep_score")
                            or row.get("Sleep Score")
                        ),
                    )
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("Stress score row error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_readiness_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Daily Readiness Score CSV files."""
    total = 0
    batch: list[ReadinessScore] = []

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                date_str = (
                    row.get("date")
                    or row.get("Date")
                    or row.get("timestamp")
                    or row.get("Timestamp")
                    or ""
                )
                if not date_str:
                    continue

                record_date = _parse_date_from_string(date_str.split("T")[0].split(" ")[0])

                score = _safe_float(
                    row.get("readiness_score")
                    or row.get("Readiness Score")
                    or row.get("score")
                    or row.get("Score")
                    or row.get("overall_score")
                )
                if score is None:
                    continue

                batch.append(
                    ReadinessScore(date=record_date, readiness_score=score)
                )

                if len(batch) >= BATCH_SIZE:
                    total += _flush_batch(db, batch)
            except Exception as exc:
                logger.debug("Readiness row error: %s", exc)
                continue

    total += _flush_batch(db, batch)
    return total


def _parse_sleep_score_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse sleep_score.csv and merge scores into existing SleepLog records.

    Returns the count of SleepLog records updated.
    """
    total = 0

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                date_str = (
                    row.get("timestamp")
                    or row.get("sleep_log_entry_id")  # sometimes this is the date field
                    or row.get("date")
                    or row.get("Date")
                    or ""
                )
                if not date_str:
                    continue

                # Try to extract a date from the string
                record_date = _parse_date_from_string(
                    date_str.split("T")[0].split(" ")[0]
                )

                overall = _safe_int(
                    row.get("overall_score")
                    or row.get("Overall Score")
                    or row.get("sleep_quality_score")
                    or row.get("total_score")
                )
                composition = _safe_int(
                    row.get("composition_score")
                    or row.get("Composition Score")
                )
                revitalization = _safe_int(
                    row.get("revitalization_score")
                    or row.get("Revitalization Score")
                )
                duration_score = _safe_int(
                    row.get("duration_score")
                    or row.get("Duration Score")
                )

                # Find matching sleep log for this date and update
                sleep_log = (
                    db.query(SleepLog)
                    .filter(SleepLog.date == record_date)
                    .first()
                )
                if sleep_log:
                    if overall is not None:
                        sleep_log.overall_score = overall
                    if composition is not None:
                        sleep_log.composition_score = composition
                    if revitalization is not None:
                        sleep_log.revitalization_score = revitalization
                    if duration_score is not None:
                        sleep_log.duration_score = duration_score
                    db.commit()
                    total += 1
            except Exception as exc:
                db.rollback()
                logger.debug("Sleep score row error: %s", exc)
                continue

    return total


def _parse_azm_csv(
    zf: zipfile.ZipFile, files: list[str], db: Session
) -> int:
    """Parse Active Zone Minutes CSV files into ActivityDaily.

    Updates existing ActivityDaily records or creates stubs with just AZM data.
    """
    total = 0

    for path in files:
        try:
            rows = _read_csv_rows(zf, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        for row in rows:
            try:
                date_str = (
                    row.get("date")
                    or row.get("Date")
                    or row.get("timestamp")
                    or row.get("Timestamp")
                    or ""
                )
                if not date_str:
                    continue

                record_date = _parse_date_from_string(
                    date_str.split("T")[0].split(" ")[0]
                )

                azm_value = _safe_int(
                    row.get("total_minutes")
                    or row.get("Total Minutes")
                    or row.get("active_zone_minutes")
                    or row.get("Active Zone Minutes")
                    or row.get("totalMinutes")
                )
                if azm_value is None:
                    # Try summing fat_burn + cardio + peak columns
                    fb = _safe_int(
                        row.get("fat_burn_minutes")
                        or row.get("Fat Burn Minutes")
                        or row.get("fatBurnActiveZoneMinutes"), 0
                    )
                    cardio = _safe_int(
                        row.get("cardio_minutes")
                        or row.get("Cardio Minutes")
                        or row.get("cardioActiveZoneMinutes"), 0
                    )
                    peak = _safe_int(
                        row.get("peak_minutes")
                        or row.get("Peak Minutes")
                        or row.get("peakActiveZoneMinutes"), 0
                    )
                    azm_value = fb + cardio + peak
                    if azm_value == 0:
                        continue

                # Upsert into ActivityDaily
                existing = (
                    db.query(ActivityDaily)
                    .filter(ActivityDaily.date == record_date)
                    .first()
                )
                if existing:
                    existing.active_zone_minutes = azm_value
                else:
                    db.add(
                        ActivityDaily(
                            date=record_date, active_zone_minutes=azm_value
                        )
                    )
                db.commit()
                total += 1
            except Exception as exc:
                db.rollback()
                logger.debug("AZM row error: %s", exc)
                continue

    return total


def _aggregate_daily_activity(db: Session) -> int:
    """Build ActivityDaily summaries by aggregating ActivityIntraday data.

    For each date that has intraday data but no daily record, create one
    by summing the intraday values. For existing records, fill in missing
    fields. Returns number of daily records created or updated.
    """
    from sqlalchemy import func, cast, Date as SADate

    count = 0

    # Get distinct dates and metrics from intraday data
    date_metrics = (
        db.query(
            func.date(ActivityIntraday.timestamp).label("day"),
            ActivityIntraday.metric,
            func.sum(ActivityIntraday.value).label("total"),
        )
        .group_by(func.date(ActivityIntraday.timestamp), ActivityIntraday.metric)
        .all()
    )

    # Organize by date
    daily_data: dict[str, dict[str, float]] = {}
    for row in date_metrics:
        day_str = str(row.day)
        if day_str not in daily_data:
            daily_data[day_str] = {}
        daily_data[day_str][row.metric] = row.total

    for day_str, metrics in daily_data.items():
        try:
            record_date = _parse_date_from_string(day_str)
            existing = (
                db.query(ActivityDaily)
                .filter(ActivityDaily.date == record_date)
                .first()
            )

            if existing:
                if existing.steps is None and "steps" in metrics:
                    existing.steps = _safe_int(metrics["steps"])
                if existing.calories_total is None and "calories" in metrics:
                    existing.calories_total = _safe_int(metrics["calories"])
                if existing.distance_km is None and "distance" in metrics:
                    existing.distance_km = metrics.get("distance")
            else:
                db.add(
                    ActivityDaily(
                        date=record_date,
                        steps=_safe_int(metrics.get("steps")),
                        calories_total=_safe_int(metrics.get("calories")),
                        distance_km=metrics.get("distance"),
                    )
                )
            db.commit()
            count += 1
        except Exception as exc:
            db.rollback()
            logger.debug("Daily aggregation error for %s: %s", day_str, exc)
            continue

    return count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_export_zip(zip_path: str, db: Session) -> dict[str, int]:
    """Parse a Google Takeout or legacy Fitbit export ZIP file.

    Extracts and imports all recognized data types into the database using
    the provided SQLAlchemy session.

    Args:
        zip_path: Absolute path to the .zip file.
        db: An active SQLAlchemy Session.

    Returns:
        A dict mapping data-type names to the count of records imported.
        Example::

            {
                "heart_rate_intraday": 145230,
                "sleep_logs": 42,
                "steps_intraday": 52000,
                "calories_intraday": 52000,
                ...
            }
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    summary: dict[str, int] = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        base = _find_base_path(zf)
        logger.info("Detected base path in ZIP: %r", base)

        # --- Global Export Data (JSON) ---
        global_dir = "Global Export Data/"

        # Heart rate
        hr_files = _list_files(zf, base, global_dir, ".json")
        hr_files = [f for f in hr_files if os.path.basename(f).startswith("heart_rate-")]
        if hr_files:
            logger.info("Parsing %d heart rate files...", len(hr_files))
            summary["heart_rate_intraday"] = _parse_heart_rate_json(zf, hr_files, db)

        # Sleep
        sleep_files = _list_files(zf, base, global_dir, ".json")
        sleep_files = [f for f in sleep_files if os.path.basename(f).startswith("sleep-")]
        if sleep_files:
            logger.info("Parsing %d sleep files...", len(sleep_files))
            summary["sleep_logs"] = _parse_sleep_json(zf, sleep_files, db)

        # Steps
        steps_files = _list_files(zf, base, global_dir, ".json")
        steps_files = [f for f in steps_files if os.path.basename(f).startswith("steps-")]
        if steps_files:
            logger.info("Parsing %d steps files...", len(steps_files))
            summary["steps_intraday"] = _parse_activity_json(zf, steps_files, "steps", db)

        # Calories
        cal_files = _list_files(zf, base, global_dir, ".json")
        cal_files = [f for f in cal_files if os.path.basename(f).startswith("calories-")]
        if cal_files:
            logger.info("Parsing %d calories files...", len(cal_files))
            summary["calories_intraday"] = _parse_activity_json(zf, cal_files, "calories", db)

        # Distance
        dist_files = _list_files(zf, base, global_dir, ".json")
        dist_files = [f for f in dist_files if os.path.basename(f).startswith("distance-")]
        if dist_files:
            logger.info("Parsing %d distance files...", len(dist_files))
            summary["distance_intraday"] = _parse_activity_json(zf, dist_files, "distance", db)

        # Altitude
        alt_files = _list_files(zf, base, global_dir, ".json")
        alt_files = [f for f in alt_files if os.path.basename(f).startswith("altitude-")]
        if alt_files:
            logger.info("Parsing %d altitude files...", len(alt_files))
            summary["altitude_intraday"] = _parse_activity_json(zf, alt_files, "altitude", db)

        # Exercise
        ex_files = _list_files(zf, base, global_dir, ".json")
        ex_files = [f for f in ex_files if os.path.basename(f).startswith("exercise-")]
        if ex_files:
            logger.info("Parsing %d exercise files...", len(ex_files))
            summary["exercises"] = _parse_exercise_json(zf, ex_files, db)

        # --- Heart Rate Variability (CSV) ---
        hrv_dir = "Heart Rate Variability/"
        hrv_daily_files = [
            f
            for f in _list_files(zf, base, hrv_dir, ".csv")
            if "Summary" in os.path.basename(f) or "summary" in os.path.basename(f)
        ]
        hrv_detail_files = [
            f
            for f in _list_files(zf, base, hrv_dir, ".csv")
            if "Details" in os.path.basename(f) or "details" in os.path.basename(f)
        ]
        if hrv_daily_files:
            logger.info("Parsing %d HRV daily summary files...", len(hrv_daily_files))
            summary["hrv_daily"] = _parse_hrv_daily_csv(zf, hrv_daily_files, db)
        if hrv_detail_files:
            logger.info("Parsing %d HRV detail files...", len(hrv_detail_files))
            summary["hrv_intraday"] = _parse_hrv_details_csv(zf, hrv_detail_files, db)

        # --- Oxygen Saturation / SpO2 (CSV) ---
        spo2_dir = "Oxygen Saturation (SpO2)/"
        spo2_daily_files = [
            f
            for f in _list_files(zf, base, spo2_dir, ".csv")
            if "Daily" in os.path.basename(f) or "daily" in os.path.basename(f)
        ]
        spo2_minute_files = [
            f
            for f in _list_files(zf, base, spo2_dir, ".csv")
            if "Minute" in os.path.basename(f) or "minute" in os.path.basename(f)
        ]
        if spo2_daily_files:
            logger.info("Parsing %d SpO2 daily files...", len(spo2_daily_files))
            summary["spo2_daily"] = _parse_spo2_daily_csv(zf, spo2_daily_files, db)
        if spo2_minute_files:
            logger.info("Parsing %d SpO2 intraday files...", len(spo2_minute_files))
            summary["spo2_intraday"] = _parse_spo2_intraday_csv(zf, spo2_minute_files, db)

        # --- Temperature (CSV) ---
        temp_dir = "Temperature/"
        temp_files = _list_files(zf, base, temp_dir, ".csv")
        if temp_files:
            logger.info("Parsing %d temperature files...", len(temp_files))
            summary["skin_temperature"] = _parse_temperature_csv(zf, temp_files, db)

        # --- Stress Score (CSV) ---
        stress_dir = "Stress Score/"
        stress_files = _list_files(zf, base, stress_dir, ".csv")
        if stress_files:
            logger.info("Parsing %d stress score files...", len(stress_files))
            summary["stress_score"] = _parse_stress_csv(zf, stress_files, db)

        # --- Daily Readiness (CSV) ---
        readiness_dir = "Daily Readiness/"
        readiness_files = _list_files(zf, base, readiness_dir, ".csv")
        if readiness_files:
            logger.info("Parsing %d readiness files...", len(readiness_files))
            summary["readiness_score"] = _parse_readiness_csv(zf, readiness_files, db)

        # --- Sleep Score (CSV) ---
        sleep_score_dir = "Sleep Score/"
        ss_files = _list_files(zf, base, sleep_score_dir, ".csv")
        if ss_files:
            logger.info("Parsing %d sleep score files...", len(ss_files))
            summary["sleep_scores_updated"] = _parse_sleep_score_csv(zf, ss_files, db)

        # --- Active Zone Minutes (CSV) ---
        azm_dir = "Active Zone Minutes (AZM)/"
        azm_files = _list_files(zf, base, azm_dir, ".csv")
        if azm_files:
            logger.info("Parsing %d AZM files...", len(azm_files))
            summary["active_zone_minutes"] = _parse_azm_csv(zf, azm_files, db)

        # --- Aggregate daily activity from intraday data ---
        logger.info("Aggregating daily activity summaries...")
        summary["activity_daily_aggregated"] = _aggregate_daily_activity(db)

    # Filter out zero-count entries for a cleaner summary
    summary = {k: v for k, v in summary.items() if v > 0}

    logger.info("Import complete. Summary: %s", summary)
    return summary
