"""
Tests for the CGM CSV parser.
"""

from io import StringIO
from datetime import datetime

import pytest
from app.parsers.export_parser import parse_cgm_csv


def test_parse_cgm_csv():
    """Test parsing CGM export CSV with GlucoseMeasurement rows."""
    csv_content = """class,value,time,length,photo_url,description,occurred_at,body,updated_at,started_at,ended_at,created_by
GlucoseMeasurement,94,"","","","",2022-12-01 19:14:27 -0800,"","","","",""
GlucoseMeasurement,79,"","","","",2022-12-01 19:45:01 -0800,"","","","",""
StepCountMeasurement,2318,"","","","",2022-12-01 20:59:59 -0800,"","","","",""
GlucoseMeasurement,55,"","","","",2022-12-01 20:00:01 -0800,"","","","",""
"""
    readings = parse_cgm_csv(StringIO(csv_content))

    assert len(readings) == 3  # Only glucose, not steps
    assert readings[0]["value"] == 94
    assert readings[0]["timestamp"].year == 2022
    assert readings[0]["timestamp"].month == 12
    assert readings[0]["source"] == "csv_import"


def test_parse_cgm_csv_empty():
    """Test parsing empty CSV returns empty list."""
    csv_content = """class,value,time,length,photo_url,description,occurred_at,body,updated_at,started_at,ended_at,created_by
"""
    readings = parse_cgm_csv(StringIO(csv_content))
    assert len(readings) == 0


def test_parse_cgm_csv_no_glucose():
    """Test parsing CSV with no GlucoseMeasurement rows returns empty list."""
    csv_content = """class,value,time,length,photo_url,description,occurred_at,body,updated_at,started_at,ended_at,created_by
StepCountMeasurement,2318,"","","","",2022-12-01 20:59:59 -0800,"","","","",""
HeartRateMeasurement,72,"","","","",2022-12-01 20:59:59 -0800,"","","","",""
"""
    readings = parse_cgm_csv(StringIO(csv_content))
    assert len(readings) == 0


def test_parse_cgm_csv_handles_invalid_rows():
    """Test parser skips invalid rows gracefully."""
    csv_content = """class,value,time,length,photo_url,description,occurred_at,body,updated_at,started_at,ended_at,created_by
GlucoseMeasurement,94,"","","","",2022-12-01 19:14:27 -0800,"","","","",""
GlucoseMeasurement,invalid_value,"","","","",2022-12-01 19:45:01 -0800,"","","","",""
GlucoseMeasurement,100,"","","","",invalid_date,"","","","",""
GlucoseMeasurement,85,"","","","",2022-12-01 20:00:01 -0800,"","","","",""
"""
    readings = parse_cgm_csv(StringIO(csv_content))
    # Should only parse rows 1 and 4 (valid ones)
    assert len(readings) == 2
    assert readings[0]["value"] == 94
    assert readings[1]["value"] == 85
