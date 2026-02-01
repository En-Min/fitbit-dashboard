"""
Tests for the GlucoseReading model.
"""

from datetime import datetime

import pytest
from app.models import GlucoseReading


def test_glucose_reading_model(db):
    """Test that GlucoseReading can be created, saved, and queried."""
    reading = GlucoseReading(
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        value=95,
        source="csv_import"
    )
    db.add(reading)
    db.commit()

    result = db.query(GlucoseReading).first()
    assert result.value == 95
    assert result.source == "csv_import"
    assert result.timestamp.hour == 10
    assert result.id is not None


def test_glucose_reading_timestamp_index(db):
    """Test that multiple readings with same timestamp are rejected (unique index)."""
    reading1 = GlucoseReading(
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        value=95,
        source="csv_import"
    )
    db.add(reading1)
    db.commit()

    reading2 = GlucoseReading(
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        value=100,
        source="csv_import"
    )
    db.add(reading2)

    with pytest.raises(Exception):
        db.commit()
