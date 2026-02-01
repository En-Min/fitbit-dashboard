"""
Tests for the glucose data API endpoints.

Covers:
  - GET /api/data/glucose - single day readings
  - GET /api/data/glucose/daily - daily summaries
  - GET /api/data/glucose/time-in-range - time in range statistics
  - GET /api/data/glucose/agp - AGP percentile data
  - Correlations with avg_glucose metric
"""

from datetime import datetime, date

import pytest
from app.models import GlucoseReading, HeartRateDaily


# ======================================================================
# Task 4: Glucose Data Endpoints
# ======================================================================

class TestGetGlucoseReadings:
    """Tests for GET /api/data/glucose?date=YYYY-MM-DD"""

    def test_get_glucose_readings(self, client, db):
        """Test retrieving glucose readings for a specific day."""
        # Add test data
        readings = [
            GlucoseReading(timestamp=datetime(2024, 1, 15, 10, 0), value=90, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 10, 15), value=95, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 10, 30), value=110, source="test"),
        ]
        for r in readings:
            db.add(r)
        db.commit()

        response = client.get("/api/data/glucose?date=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert len(data["readings"]) == 3
        assert data["readings"][0]["value"] == 90

    def test_get_glucose_readings_empty_day(self, client, db):
        """Test retrieving glucose readings for a day with no data."""
        response = client.get("/api/data/glucose?date=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert data["readings"] == []

    def test_get_glucose_readings_filters_by_date(self, client, db):
        """Test that only readings from the specified date are returned."""
        # Add data on different days
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 14, 23, 0), value=80, source="test"))
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"))
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 16, 1, 0), value=120, source="test"))
        db.commit()

        response = client.get("/api/data/glucose?date=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert len(data["readings"]) == 1
        assert data["readings"][0]["value"] == 100

    def test_get_glucose_readings_missing_date_param(self, client):
        """Test that missing date parameter returns 422."""
        response = client.get("/api/data/glucose")
        assert response.status_code == 422


class TestGetGlucoseDaily:
    """Tests for GET /api/data/glucose/daily?start=&end="""

    def test_get_glucose_daily_summary(self, client, db):
        """Test daily glucose summary calculation."""
        # Add readings for calculating daily stats
        readings = [
            GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=70, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 18, 0), value=150, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 22, 0), value=80, source="test"),
        ]
        for r in readings:
            db.add(r)
        db.commit()

        response = client.get("/api/data/glucose/daily?start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["avg"] == 100  # (70+100+150+80)/4
        assert data[0]["min"] == 70
        assert data[0]["max"] == 150
        assert data[0]["count"] == 4

    def test_get_glucose_daily_multiple_days(self, client, db):
        """Test daily summary for multiple days."""
        # Day 1
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"))
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 18, 0), value=120, source="test"))
        # Day 2
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 16, 12, 0), value=90, source="test"))
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 16, 18, 0), value=110, source="test"))
        db.commit()

        response = client.get("/api/data/glucose/daily?start=2024-01-15&end=2024-01-16")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["date"] == "2024-01-15"
        assert data[0]["avg"] == 110  # (100+120)/2
        assert data[1]["date"] == "2024-01-16"
        assert data[1]["avg"] == 100  # (90+110)/2

    def test_get_glucose_daily_empty(self, client, db):
        """Test daily summary with no data."""
        response = client.get("/api/data/glucose/daily?start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetGlucoseTimeInRange:
    """Tests for GET /api/data/glucose/time-in-range?start=&end="""

    def test_get_glucose_time_in_range(self, client, db):
        """Test time-in-range calculation."""
        # 4 readings: 1 low (<70), 2 in range (70-180), 1 high (>180)
        readings = [
            GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=60, source="test"),   # low
            GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"), # in range
            GlucoseReading(timestamp=datetime(2024, 1, 15, 16, 0), value=120, source="test"), # in range
            GlucoseReading(timestamp=datetime(2024, 1, 15, 20, 0), value=200, source="test"), # high
        ]
        for r in readings:
            db.add(r)
        db.commit()

        response = client.get("/api/data/glucose/time-in-range?start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert data["in_range_percent"] == 50.0
        assert data["low_percent"] == 25.0
        assert data["high_percent"] == 25.0
        assert data["total_readings"] == 4

    def test_get_glucose_time_in_range_empty(self, client, db):
        """Test time-in-range with no data."""
        response = client.get("/api/data/glucose/time-in-range?start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert data["total_readings"] == 0
        assert data["in_range_percent"] == 0
        assert data["low_percent"] == 0
        assert data["high_percent"] == 0

    def test_get_glucose_time_in_range_all_in_range(self, client, db):
        """Test when all readings are in range."""
        readings = [
            GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=100, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=120, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 16, 0), value=140, source="test"),
        ]
        for r in readings:
            db.add(r)
        db.commit()

        response = client.get("/api/data/glucose/time-in-range?start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert data["in_range_percent"] == 100.0
        assert data["low_percent"] == 0.0
        assert data["high_percent"] == 0.0

    def test_get_glucose_time_in_range_custom_thresholds(self, client, db):
        """Test time-in-range with custom thresholds."""
        # With default thresholds (70-180): 2 in range, 1 high
        # With custom thresholds (80-150): 1 in range, 2 high
        readings = [
            GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=100, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=160, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 16, 0), value=170, source="test"),
        ]
        for r in readings:
            db.add(r)
        db.commit()

        response = client.get("/api/data/glucose/time-in-range?start=2024-01-15&end=2024-01-15&low_threshold=80&high_threshold=150")
        assert response.status_code == 200
        data = response.json()
        assert data["high_percent"] == pytest.approx(66.7, rel=0.1)


# ======================================================================
# Task 5: AGP Endpoint
# ======================================================================

class TestGetGlucoseAGP:
    """Tests for GET /api/data/glucose/agp?start=&end="""

    def test_get_glucose_agp(self, client, db):
        """AGP calculates percentiles for each time slot across multiple days."""
        # Day 1: 8am=80, 12pm=100
        # Day 2: 8am=90, 12pm=110
        readings = [
            GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=80, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 16, 8, 0), value=90, source="test"),
            GlucoseReading(timestamp=datetime(2024, 1, 16, 12, 0), value=110, source="test"),
        ]
        for r in readings:
            db.add(r)
        db.commit()

        response = client.get("/api/data/glucose/agp?start=2024-01-15&end=2024-01-16")
        assert response.status_code == 200
        data = response.json()

        # Should have 24 hourly buckets
        assert len(data["hourly"]) == 24

        # Check 8am bucket (hour 8)
        hour_8 = next(h for h in data["hourly"] if h["hour"] == 8)
        assert hour_8["median"] == 85  # median of [80, 90]
        assert hour_8["p10"] <= hour_8["p25"] <= hour_8["median"] <= hour_8["p75"] <= hour_8["p90"]
        assert hour_8["count"] == 2

    def test_get_glucose_agp_empty(self, client, db):
        """Test AGP with no data."""
        response = client.get("/api/data/glucose/agp?start=2024-01-15&end=2024-01-16")
        assert response.status_code == 200
        data = response.json()
        assert len(data["hourly"]) == 24
        # All hours should have null values
        for hour_data in data["hourly"]:
            assert hour_data["median"] is None
            assert hour_data["count"] == 0

    def test_get_glucose_agp_single_reading_per_hour(self, client, db):
        """Test AGP with single reading per hour."""
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 10, 0), value=100, source="test"))
        db.commit()

        response = client.get("/api/data/glucose/agp?start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()

        hour_10 = next(h for h in data["hourly"] if h["hour"] == 10)
        # With single value, all percentiles should be the same
        assert hour_10["median"] == 100
        assert hour_10["p10"] == 100
        assert hour_10["p90"] == 100


# ======================================================================
# Task 6: Correlations with Glucose
# ======================================================================

class TestCorrelationsWithGlucose:
    """Tests for glucose in correlation endpoint."""

    def test_correlations_with_glucose(self, client, db):
        """Test that glucose can be correlated with other metrics."""
        # Add glucose and heart rate for same dates
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"))
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 16, 12, 0), value=110, source="test"))
        db.add(HeartRateDaily(date=date(2024, 1, 15), resting_heart_rate=60))
        db.add(HeartRateDaily(date=date(2024, 1, 16), resting_heart_rate=65))
        db.commit()

        response = client.get("/api/data/correlations?x=avg_glucose&y=resting_hr&start=2024-01-15&end=2024-01-16")
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 2
        assert "avg_glucose" in data["availableMetrics"]

    def test_correlations_glucose_as_y_metric(self, client, db):
        """Test glucose as the Y metric in correlation."""
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"))
        db.add(HeartRateDaily(date=date(2024, 1, 15), resting_heart_rate=60))
        db.commit()

        response = client.get("/api/data/correlations?x=resting_hr&y=avg_glucose&start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 1
        assert data["points"][0]["x"] == 60
        assert data["points"][0]["y"] == 100

    def test_correlations_glucose_daily_averaging(self, client, db):
        """Test that multiple glucose readings on same day are averaged."""
        # Multiple readings on same day
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=80, source="test"))
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"))
        db.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 18, 0), value=120, source="test"))
        db.add(HeartRateDaily(date=date(2024, 1, 15), resting_heart_rate=60))
        db.commit()

        response = client.get("/api/data/correlations?x=avg_glucose&y=resting_hr&start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 1
        # Average of 80, 100, 120 = 100
        assert data["points"][0]["x"] == 100

    def test_correlations_glucose_no_data(self, client, db):
        """Test correlation with glucose when no glucose data exists."""
        db.add(HeartRateDaily(date=date(2024, 1, 15), resting_heart_rate=60))
        db.commit()

        response = client.get("/api/data/correlations?x=avg_glucose&y=resting_hr&start=2024-01-15&end=2024-01-15")
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 0
