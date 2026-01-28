"""
Tests for the FastAPI REST endpoints defined in app.routers.data and app.main.

Covers:
  - Health check
  - Metrics listing
  - Overview endpoint
  - All data-type GET endpoints (heart rate, sleep, SpO2, HRV, etc.)
  - Correlation endpoint (valid + invalid metrics)
  - Empty-database responses
  - Date-range filtering
"""

from datetime import date, datetime

import pytest
from app import models


# ======================================================================
# Health check
# ======================================================================

class TestHealthCheck:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ======================================================================
# Metrics
# ======================================================================

class TestMetrics:
    def test_metrics_empty_db(self, client):
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert data["metrics"] == []

    def test_metrics_with_data(self, client, sample_data):
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        names = [m["name"] for m in data["metrics"]]
        # All populated metric types should appear
        for expected in [
            "heart_rate_intraday", "heart_rate_daily", "sleep",
            "spo2", "hrv", "breathing_rate", "skin_temperature",
            "vo2_max", "activity", "stress", "readiness", "exercises",
        ]:
            assert expected in names, f"{expected} should appear in metrics"

    def test_metrics_format(self, client, sample_data):
        resp = client.get("/api/metrics")
        for m in resp.json()["metrics"]:
            assert "name" in m
            assert "label" in m
            assert "unit" in m
            assert "startDate" in m
            assert "endDate" in m
            assert "count" in m
            assert isinstance(m["count"], int)
            assert m["count"] > 0


# ======================================================================
# Overview
# ======================================================================

class TestOverview:
    def test_overview_with_data(self, client, sample_data):
        resp = client.get("/api/data/overview", params={"date": "2024-06-15"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2024-06-15"

        # Heart rate
        assert data["heartRate"] is not None
        assert data["heartRate"]["resting_heart_rate"] == 62

        # Sleep
        assert data["sleep"] is not None
        assert data["sleep"]["minutes_asleep"] == 420
        assert data["sleep"]["overall_score"] == 85

        # Activity
        assert data["activity"] is not None
        assert data["activity"]["steps"] == 10500

        # SpO2
        assert data["spo2"] is not None
        assert data["spo2"]["avg_spo2"] == 97.2

        # HRV
        assert data["hrv"] is not None
        assert data["hrv"]["daily_rmssd"] == 42.5

        # Breathing rate
        assert data["breathingRate"] is not None
        assert data["breathingRate"]["breathing_rate"] == 15.2

        # Skin temperature
        assert data["skinTemperature"] is not None
        assert data["skinTemperature"]["relative_temp"] == -0.3

        # VO2 Max
        assert data["vo2Max"] is not None
        assert data["vo2Max"]["vo2_max"] == 45.0

        # Stress
        assert data["stress"] is not None
        assert data["stress"]["stress_score"] == 75

        # Readiness
        assert data["readiness"] is not None
        assert data["readiness"]["readiness_score"] == 82.0

    def test_overview_empty_date(self, client):
        resp = client.get("/api/data/overview", params={"date": "2020-01-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["heartRate"] is None
        assert data["sleep"] is None
        assert data["activity"] is None

    def test_overview_defaults_to_today(self, client):
        resp = client.get("/api/data/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == str(date.today())


# ======================================================================
# Heart Rate
# ======================================================================

class TestHeartRateIntraday:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/heart-rate/intraday", params={"date": "2024-06-15"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2024-06-15"
        assert len(data["data"]) == 2
        assert data["data"][0]["bpm"] == 72
        assert data["data"][1]["bpm"] == 74

    def test_empty_date(self, client, sample_data):
        resp = client.get("/api/data/heart-rate/intraday", params={"date": "2020-01-01"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_missing_date_param(self, client):
        resp = client.get("/api/data/heart-rate/intraday")
        assert resp.status_code == 422  # validation error: missing required param

    def test_data_format(self, client, sample_data):
        resp = client.get("/api/data/heart-rate/intraday", params={"date": "2024-06-15"})
        for point in resp.json()["data"]:
            assert "timestamp" in point
            assert "bpm" in point
            assert "confidence" in point


class TestHeartRateDaily:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/heart-rate/daily", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["date"] == "2024-06-15"
        assert data[0]["restingHeartRate"] == 62
        assert data[0]["fatBurnMinutes"] == 30

    def test_outside_range(self, client, sample_data):
        resp = client.get("/api/data/heart-rate/daily", params={
            "start": "2025-01-01", "end": "2025-01-31"
        })
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_defaults_to_last_7_days(self, client):
        resp = client.get("/api/data/heart-rate/daily")
        assert resp.status_code == 200
        assert "data" in resp.json()


# ======================================================================
# Sleep
# ======================================================================

class TestSleep:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/sleep", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["date"] == "2024-06-15"
        assert data[0]["minutesAsleep"] == 420
        assert data[0]["overallScore"] == 85
        assert data[0]["deepSleepMinutes"] == 90

    def test_empty_range(self, client, sample_data):
        resp = client.get("/api/data/sleep", params={
            "start": "2020-01-01", "end": "2020-01-31"
        })
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_sleep_data_format(self, client, sample_data):
        resp = client.get("/api/data/sleep", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        record = resp.json()["data"][0]
        assert "id" in record
        assert "startTime" in record
        assert "endTime" in record
        assert "durationMs" in record
        assert "efficiency" in record


class TestSleepStages:
    def test_with_data(self, client, sample_data):
        sleep_id = sample_data["sleep"].id
        resp = client.get(f"/api/data/sleep/stages/{sleep_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        stages = [d["stage"] for d in data]
        assert "light" in stages
        assert "deep" in stages

    def test_nonexistent_sleep_id(self, client, sample_data):
        resp = client.get("/api/data/sleep/stages/99999")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_stage_data_format(self, client, sample_data):
        sleep_id = sample_data["sleep"].id
        resp = client.get(f"/api/data/sleep/stages/{sleep_id}")
        for stage in resp.json()["data"]:
            assert "timestamp" in stage
            assert "stage" in stage
            assert "durationSeconds" in stage


# ======================================================================
# SpO2
# ======================================================================

class TestSpO2:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/spo2", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["date"] == "2024-06-15"
        assert data[0]["avg"] == 97.2
        assert data[0]["min"] == 94.0
        assert data[0]["max"] == 99.0

    def test_empty(self, client):
        resp = client.get("/api/data/spo2", params={
            "start": "2020-01-01", "end": "2020-01-31"
        })
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ======================================================================
# HRV
# ======================================================================

class TestHRV:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/hrv", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["date"] == "2024-06-15"
        assert data[0]["dailyRmssd"] == 42.5
        assert data[0]["deepRmssd"] == 55.0

    def test_empty(self, client):
        resp = client.get("/api/data/hrv", params={
            "start": "2020-01-01", "end": "2020-01-31"
        })
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ======================================================================
# Breathing Rate
# ======================================================================

class TestBreathingRate:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/breathing-rate", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["breathingRate"] == 15.2

    def test_empty(self, client):
        resp = client.get("/api/data/breathing-rate")
        assert resp.status_code == 200
        assert "data" in resp.json()


# ======================================================================
# Skin Temperature
# ======================================================================

class TestSkinTemperature:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/skin-temperature", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["relativeTemp"] == -0.3

    def test_empty(self, client):
        resp = client.get("/api/data/skin-temperature")
        assert resp.status_code == 200
        assert "data" in resp.json()


# ======================================================================
# VO2 Max
# ======================================================================

class TestVO2Max:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/vo2-max", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["vo2Max"] == 45.0

    def test_empty(self, client):
        resp = client.get("/api/data/vo2-max")
        assert resp.status_code == 200
        assert "data" in resp.json()


# ======================================================================
# Activity
# ======================================================================

class TestActivityDaily:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/activity", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["steps"] == 10500
        assert data[0]["distanceKm"] == 8.2
        assert data[0]["caloriesTotal"] == 2400
        assert data[0]["activeZoneMinutes"] == 50

    def test_empty(self, client):
        resp = client.get("/api/data/activity")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestActivityIntraday:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/activity/intraday", params={
            "date": "2024-06-15", "metric": "steps"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["value"] == 120.0

    def test_wrong_metric(self, client, sample_data):
        resp = client.get("/api/data/activity/intraday", params={
            "date": "2024-06-15", "metric": "calories"
        })
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_missing_date(self, client):
        resp = client.get("/api/data/activity/intraday")
        assert resp.status_code == 422


# ======================================================================
# Stress
# ======================================================================

class TestStress:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/stress", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["stressScore"] == 75
        assert data[0]["exertionScore"] == 20

    def test_empty(self, client):
        resp = client.get("/api/data/stress")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ======================================================================
# Exercises
# ======================================================================

class TestExercises:
    def test_with_data(self, client, sample_data):
        resp = client.get("/api/data/exercises", params={
            "start": "2024-06-01", "end": "2024-06-30"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["activityName"] == "Run"
        assert data[0]["calories"] == 450
        assert data[0]["steps"] == 6000

    def test_empty(self, client):
        resp = client.get("/api/data/exercises")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ======================================================================
# Correlations
# ======================================================================

class TestCorrelations:
    def test_valid_metrics(self, client, sample_data):
        resp = client.get("/api/data/correlations", params={
            "x": "resting_hr",
            "y": "steps",
            "start": "2024-06-01",
            "end": "2024-06-30",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["xMetric"] == "resting_hr"
        assert data["yMetric"] == "steps"
        assert "points" in data
        assert "correlation" in data
        assert "availableMetrics" in data
        assert len(data["points"]) == 1
        assert data["points"][0]["x"] == 62
        assert data["points"][0]["y"] == 10500

    def test_invalid_x_metric(self, client):
        resp = client.get("/api/data/correlations", params={
            "x": "nonexistent", "y": "steps",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_invalid_y_metric(self, client):
        resp = client.get("/api/data/correlations", params={
            "x": "resting_hr", "y": "nonexistent",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_no_overlapping_data(self, client, sample_data):
        resp = client.get("/api/data/correlations", params={
            "x": "resting_hr",
            "y": "steps",
            "start": "2020-01-01",
            "end": "2020-01-31",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["points"] == []
        assert data["correlation"] is None

    def test_available_metrics_listed(self, client):
        resp = client.get("/api/data/correlations", params={
            "x": "resting_hr", "y": "steps",
        })
        assert resp.status_code == 200
        available = resp.json()["availableMetrics"]
        assert "resting_hr" in available
        assert "steps" in available
        assert "hrv" in available

    def test_missing_required_params(self, client):
        resp = client.get("/api/data/correlations")
        assert resp.status_code == 422


# ======================================================================
# Empty database behavior
# ======================================================================

class TestEmptyDatabase:
    def test_all_endpoints_return_empty(self, client):
        """Every data endpoint should return 200 with empty data when no
        records exist, rather than erroring out."""
        endpoints_with_params = [
            ("/api/data/heart-rate/daily", {}),
            ("/api/data/sleep", {}),
            ("/api/data/spo2", {}),
            ("/api/data/hrv", {}),
            ("/api/data/breathing-rate", {}),
            ("/api/data/skin-temperature", {}),
            ("/api/data/vo2-max", {}),
            ("/api/data/activity", {}),
            ("/api/data/stress", {}),
            ("/api/data/exercises", {}),
        ]
        for path, params in endpoints_with_params:
            resp = client.get(path, params=params)
            assert resp.status_code == 200, f"{path} should return 200"
            body = resp.json()
            assert "data" in body, f"{path} should have 'data' key"
            assert body["data"] == [], f"{path} should return empty list"


# ======================================================================
# Date-range filtering
# ======================================================================

class TestDateRangeFiltering:
    def test_narrow_range_includes(self, client, sample_data):
        """Data on 2024-06-15 should be found with a range that includes it."""
        resp = client.get("/api/data/activity", params={
            "start": "2024-06-15", "end": "2024-06-15"
        })
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_narrow_range_excludes(self, client, sample_data):
        """Data on 2024-06-15 should not appear for an adjacent date range."""
        resp = client.get("/api/data/activity", params={
            "start": "2024-06-16", "end": "2024-06-20"
        })
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0

    def test_wide_range_includes(self, client, sample_data):
        resp = client.get("/api/data/hrv", params={
            "start": "2024-01-01", "end": "2024-12-31"
        })
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_multiple_records_filtering(self, client, db):
        """Insert records on multiple dates and confirm range filtering
        returns only those within bounds."""
        from datetime import timedelta
        base = date(2024, 3, 1)
        for i in range(10):
            db.add(models.BreathingRate(
                date=base + timedelta(days=i), breathing_rate=14.0 + i * 0.1
            ))
        db.commit()

        # Query only the first 5 days
        resp = client.get("/api/data/breathing-rate", params={
            "start": "2024-03-01", "end": "2024-03-05"
        })
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 5
