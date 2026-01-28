"""
Tests for the Fitbit export ZIP parser (app.parsers.export_parser).

Covers:
  - Timestamp / date parsing helpers
  - Safe type-conversion helpers
  - End-to-end parse_export_zip with in-memory ZIP files containing:
      - Heart rate JSON
      - Steps JSON
      - Sleep JSON
      - Empty ZIP
      - ZIP with missing data types
"""

import io
import json
import os
import tempfile
import zipfile
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.parsers.export_parser import (
    _parse_fitbit_timestamp,
    _parse_iso_timestamp,
    _parse_date_from_string,
    _safe_int,
    _safe_float,
    parse_export_zip,
)
from app import models


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_session():
    """Return a fresh in-memory SQLAlchemy session with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def _write_zip(file_map: dict[str, bytes]) -> str:
    """Create a temporary ZIP file from a dict of {internal_path: content_bytes}.

    Returns the path to the temporary file (caller should delete it).
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in file_map.items():
            zf.writestr(path, content)
    tmp.close()
    return tmp.name


# ======================================================================
# _parse_fitbit_timestamp
# ======================================================================

class TestParseFitbitTimestamp:
    def test_valid(self):
        result = _parse_fitbit_timestamp("01/15/24 08:30:00")
        assert result == datetime(2024, 1, 15, 8, 30, 0)

    def test_valid_end_of_day(self):
        result = _parse_fitbit_timestamp("12/31/23 23:59:59")
        assert result == datetime(2023, 12, 31, 23, 59, 59)

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            _parse_fitbit_timestamp("2024-01-15T08:30:00")

    def test_invalid_string(self):
        with pytest.raises(ValueError):
            _parse_fitbit_timestamp("not a timestamp")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            _parse_fitbit_timestamp("")


# ======================================================================
# _parse_iso_timestamp
# ======================================================================

class TestParseIsoTimestamp:
    def test_iso_with_millis(self):
        result = _parse_iso_timestamp("2024-01-15T08:30:00.000")
        assert result == datetime(2024, 1, 15, 8, 30, 0)

    def test_iso_without_millis(self):
        result = _parse_iso_timestamp("2024-01-15T08:30:00")
        assert result == datetime(2024, 1, 15, 8, 30, 0)

    def test_space_separated(self):
        result = _parse_iso_timestamp("2024-01-15 08:30:00")
        assert result == datetime(2024, 1, 15, 8, 30, 0)

    def test_date_only(self):
        result = _parse_iso_timestamp("2024-01-15")
        assert result == datetime(2024, 1, 15, 0, 0, 0)

    def test_fitbit_style(self):
        result = _parse_iso_timestamp("01/15/24 08:30:00")
        assert result == datetime(2024, 1, 15, 8, 30, 0)

    def test_with_whitespace(self):
        result = _parse_iso_timestamp("  2024-01-15T08:30:00  ")
        assert result == datetime(2024, 1, 15, 8, 30, 0)

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Unable to parse timestamp"):
            _parse_iso_timestamp("garbage input")


# ======================================================================
# _parse_date_from_string
# ======================================================================

class TestParseDateFromString:
    def test_iso_format(self):
        assert _parse_date_from_string("2024-06-15") == date(2024, 6, 15)

    def test_mm_dd_yy(self):
        assert _parse_date_from_string("06/15/24") == date(2024, 6, 15)

    def test_mm_dd_yyyy(self):
        assert _parse_date_from_string("06/15/2024") == date(2024, 6, 15)

    def test_with_whitespace(self):
        assert _parse_date_from_string("  2024-06-15  ") == date(2024, 6, 15)

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Unable to parse date"):
            _parse_date_from_string("not-a-date")


# ======================================================================
# _safe_int
# ======================================================================

class TestSafeInt:
    def test_int_value(self):
        assert _safe_int(42) == 42

    def test_float_value(self):
        assert _safe_int(42.9) == 42

    def test_string_int(self):
        assert _safe_int("100") == 100

    def test_string_float(self):
        assert _safe_int("99.5") == 99

    def test_none_returns_default(self):
        assert _safe_int(None) is None
        assert _safe_int(None, 0) == 0

    def test_empty_string_returns_default(self):
        assert _safe_int("") is None
        assert _safe_int("", 0) == 0

    def test_invalid_string_returns_default(self):
        assert _safe_int("abc") is None
        assert _safe_int("abc", -1) == -1

    def test_boolean_value(self):
        # bool is a subclass of int in Python; True -> 1, False -> 0
        assert _safe_int(True) == 1
        assert _safe_int(False) == 0


# ======================================================================
# _safe_float
# ======================================================================

class TestSafeFloat:
    def test_float_value(self):
        assert _safe_float(3.14) == 3.14

    def test_int_value(self):
        assert _safe_float(42) == 42.0

    def test_string_float(self):
        assert _safe_float("3.14") == 3.14

    def test_string_int(self):
        assert _safe_float("100") == 100.0

    def test_none_returns_default(self):
        assert _safe_float(None) is None
        assert _safe_float(None, 0.0) == 0.0

    def test_empty_string_returns_default(self):
        assert _safe_float("") is None
        assert _safe_float("", 0.0) == 0.0

    def test_invalid_string_returns_default(self):
        assert _safe_float("xyz") is None
        assert _safe_float("xyz", -1.0) == -1.0


# ======================================================================
# parse_export_zip -- heart rate data
# ======================================================================

class TestParseExportZipHeartRate:
    def test_heart_rate_json(self):
        """A ZIP with heart_rate-YYYY-MM-DD.json should populate HeartRateIntraday."""
        db, engine = _make_db_session()

        hr_data = [
            {
                "dateTime": "01/15/24 08:30:00",
                "value": {"bpm": 72, "confidence": 2},
            },
            {
                "dateTime": "01/15/24 08:30:05",
                "value": {"bpm": 74, "confidence": 3},
            },
        ]

        zip_path = _write_zip({
            "Takeout/Fitbit/Global Export Data/heart_rate-2024-01-15.json":
                json.dumps(hr_data).encode()
        })

        try:
            summary = parse_export_zip(zip_path, db)
            assert "heart_rate_intraday" in summary
            assert summary["heart_rate_intraday"] == 2

            rows = db.query(models.HeartRateIntraday).order_by(
                models.HeartRateIntraday.timestamp
            ).all()
            assert len(rows) == 2
            assert rows[0].bpm == 72
            assert rows[0].confidence == 2
            assert rows[1].bpm == 74
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)

    def test_heart_rate_flat_value(self):
        """Heart rate entry with value as a plain number instead of dict."""
        db, engine = _make_db_session()

        hr_data = [
            {"dateTime": "01/15/24 08:30:00", "value": 72},
        ]

        zip_path = _write_zip({
            "Takeout/Fitbit/Global Export Data/heart_rate-2024-01-15.json":
                json.dumps(hr_data).encode()
        })

        try:
            summary = parse_export_zip(zip_path, db)
            assert summary.get("heart_rate_intraday", 0) == 1
            row = db.query(models.HeartRateIntraday).first()
            assert row.bpm == 72
            assert row.confidence is None
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)


# ======================================================================
# parse_export_zip -- steps data
# ======================================================================

class TestParseExportZipSteps:
    def test_steps_json(self):
        """A ZIP with steps-YYYY-MM-DD.json should populate ActivityIntraday."""
        db, engine = _make_db_session()

        steps_data = [
            {"dateTime": "01/15/24 08:00:00", "value": "150"},
            {"dateTime": "01/15/24 08:01:00", "value": "200"},
            {"dateTime": "01/15/24 08:02:00", "value": "0"},
        ]

        zip_path = _write_zip({
            "Takeout/Fitbit/Global Export Data/steps-2024-01-15.json":
                json.dumps(steps_data).encode()
        })

        try:
            summary = parse_export_zip(zip_path, db)
            # value "0" is a valid float, so it should be inserted
            assert summary.get("steps_intraday", 0) == 3

            rows = db.query(models.ActivityIntraday).filter(
                models.ActivityIntraday.metric == "steps"
            ).all()
            assert len(rows) == 3
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)


# ======================================================================
# parse_export_zip -- sleep data
# ======================================================================

class TestParseExportZipSleep:
    def test_sleep_json(self):
        """A ZIP with sleep-YYYY-MM-DD.json should populate SleepLog and SleepStage."""
        db, engine = _make_db_session()

        sleep_data = [
            {
                "logId": 12345,
                "startTime": "2024-01-14T23:00:00.000",
                "endTime": "2024-01-15T07:00:00.000",
                "duration": 28800000,
                "efficiency": 92,
                "minutesAsleep": 420,
                "minutesAwake": 60,
                "timeInBed": 480,
                "type": "stages",
                "levels": {
                    "summary": {
                        "deep": {"minutes": 90},
                        "rem": {"minutes": 100},
                        "light": {"minutes": 230},
                    },
                    "data": [
                        {
                            "dateTime": "2024-01-14T23:00:00.000",
                            "level": "light",
                            "seconds": 1800,
                        },
                        {
                            "dateTime": "2024-01-14T23:30:00.000",
                            "level": "deep",
                            "seconds": 3600,
                        },
                    ],
                    "shortData": [],
                },
            }
        ]

        zip_path = _write_zip({
            "Takeout/Fitbit/Global Export Data/sleep-2024-01-15.json":
                json.dumps(sleep_data).encode()
        })

        try:
            summary = parse_export_zip(zip_path, db)
            assert summary.get("sleep_logs", 0) == 1

            sleep_log = db.query(models.SleepLog).first()
            assert sleep_log is not None
            assert sleep_log.log_id == "12345"
            assert sleep_log.minutes_asleep == 420
            assert sleep_log.deep_sleep_minutes == 90

            stages = db.query(models.SleepStage).filter(
                models.SleepStage.sleep_log_id == sleep_log.id
            ).order_by(models.SleepStage.timestamp).all()
            assert len(stages) == 2
            assert stages[0].stage == "light"
            assert stages[1].stage == "deep"
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)

    def test_sleep_duplicate_skipped(self):
        """Re-importing the same sleep log should not produce duplicates."""
        db, engine = _make_db_session()

        sleep_data = [
            {
                "logId": 99999,
                "startTime": "2024-02-01T22:30:00.000",
                "endTime": "2024-02-02T06:30:00.000",
                "duration": 28800000,
                "efficiency": 88,
                "minutesAsleep": 400,
                "minutesAwake": 80,
                "timeInBed": 480,
                "type": "stages",
                "levels": {"summary": {}, "data": [], "shortData": []},
            }
        ]

        content = json.dumps(sleep_data).encode()
        zip_path = _write_zip({
            "Takeout/Fitbit/Global Export Data/sleep-2024-02-01.json": content,
        })

        try:
            # First import
            parse_export_zip(zip_path, db)
            assert db.query(models.SleepLog).count() == 1

            # Second import -- should skip the duplicate
            parse_export_zip(zip_path, db)
            assert db.query(models.SleepLog).count() == 1
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)


# ======================================================================
# parse_export_zip -- empty ZIP
# ======================================================================

class TestParseExportZipEmpty:
    def test_empty_zip(self):
        """An empty ZIP file should return an empty summary without crashing."""
        db, engine = _make_db_session()

        zip_path = _write_zip({})
        try:
            summary = parse_export_zip(zip_path, db)
            assert summary == {}
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)

    def test_zip_with_unrelated_files(self):
        """A ZIP with only unrelated files should return empty summary."""
        db, engine = _make_db_session()

        zip_path = _write_zip({
            "Takeout/Fitbit/readme.txt": b"Just a readme",
            "Takeout/Fitbit/Global Export Data/some_other_file.txt": b"nope",
        })
        try:
            summary = parse_export_zip(zip_path, db)
            assert summary == {}
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)


# ======================================================================
# parse_export_zip -- missing data types should not crash
# ======================================================================

class TestParseExportZipMissingTypes:
    def test_only_heart_rate_no_crash(self):
        """A ZIP that has heart rate but no sleep/steps/etc. should not crash."""
        db, engine = _make_db_session()

        hr_data = [
            {"dateTime": "06/01/24 10:00:00", "value": {"bpm": 68, "confidence": 1}},
        ]

        zip_path = _write_zip({
            "Takeout/Fitbit/Global Export Data/heart_rate-2024-06-01.json":
                json.dumps(hr_data).encode()
        })

        try:
            summary = parse_export_zip(zip_path, db)
            assert "heart_rate_intraday" in summary
            assert summary["heart_rate_intraday"] == 1
            # No other keys should appear (no sleep, steps, etc.)
            for key in ["sleep_logs", "steps_intraday", "calories_intraday"]:
                assert key not in summary
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)


# ======================================================================
# parse_export_zip -- file not found
# ======================================================================

class TestParseExportZipErrors:
    def test_file_not_found(self):
        """parse_export_zip should raise FileNotFoundError for a missing file."""
        db, engine = _make_db_session()
        try:
            with pytest.raises(FileNotFoundError):
                parse_export_zip("/tmp/nonexistent_fitbit_export.zip", db)
        finally:
            db.close()
            engine.dispose()


# ======================================================================
# parse_export_zip -- old Fitbit layout
# ======================================================================

class TestParseExportZipOldLayout:
    def test_old_fitbit_layout(self):
        """Files under MyFitbitData/ should also be detected and parsed."""
        db, engine = _make_db_session()

        hr_data = [
            {"dateTime": "03/10/24 12:00:00", "value": {"bpm": 80, "confidence": 2}},
        ]

        zip_path = _write_zip({
            "MyFitbitData/Global Export Data/heart_rate-2024-03-10.json":
                json.dumps(hr_data).encode()
        })

        try:
            summary = parse_export_zip(zip_path, db)
            assert summary.get("heart_rate_intraday", 0) == 1
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)


# ======================================================================
# parse_export_zip -- exercise data
# ======================================================================

class TestParseExportZipExercise:
    def test_exercise_json(self):
        """Exercise JSON files should populate the Exercise table."""
        db, engine = _make_db_session()

        ex_data = [
            {
                "logId": 55555,
                "startTime": "2024-04-01T07:00:00.000",
                "endTime": "2024-04-01T08:00:00.000",
                "activityName": "Run",
                "activeDuration": 3600000,
                "calories": 500,
                "averageHeartRate": 150,
                "steps": 7000,
                "distance": 6.2,
            }
        ]

        zip_path = _write_zip({
            "Takeout/Fitbit/Global Export Data/exercise-2024-04-01.json":
                json.dumps(ex_data).encode()
        })

        try:
            summary = parse_export_zip(zip_path, db)
            assert summary.get("exercises", 0) == 1

            ex = db.query(models.Exercise).first()
            assert ex is not None
            assert ex.activity_name == "Run"
            assert ex.calories == 500
            assert ex.steps == 7000
        finally:
            db.close()
            engine.dispose()
            os.unlink(zip_path)
