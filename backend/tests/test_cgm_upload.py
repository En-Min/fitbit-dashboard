"""
Tests for the CGM upload endpoint.
"""

from io import BytesIO

import pytest
from app.models import GlucoseReading


def test_upload_cgm_csv(client, db):
    """Test uploading a CGM CSV file imports glucose readings."""
    csv_content = b"""class,value,time,length,photo_url,description,occurred_at,body,updated_at,started_at,ended_at,created_by
GlucoseMeasurement,94,"","","","",2022-12-01 19:14:27 -0800,"","","","",""
GlucoseMeasurement,79,"","","","",2022-12-01 19:45:01 -0800,"","","","",""
"""

    response = client.post(
        "/api/upload/cgm",
        files={"file": ("cgm_data.csv", BytesIO(csv_content), "text/csv")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["readings_imported"] == 2
    assert data["source"] == "csv_import"

    # Verify data in database
    readings = db.query(GlucoseReading).all()
    assert len(readings) == 2


def test_upload_cgm_csv_avoids_duplicates(client, db):
    """Test uploading same CSV twice doesn't create duplicates."""
    csv_content = b"""class,value,time,length,photo_url,description,occurred_at,body,updated_at,started_at,ended_at,created_by
GlucoseMeasurement,94,"","","","",2022-12-01 19:14:27 -0800,"","","","",""
"""

    # First upload
    response1 = client.post(
        "/api/upload/cgm",
        files={"file": ("cgm_data.csv", BytesIO(csv_content), "text/csv")}
    )
    assert response1.status_code == 200
    assert response1.json()["readings_imported"] == 1

    # Second upload of same data
    response2 = client.post(
        "/api/upload/cgm",
        files={"file": ("cgm_data.csv", BytesIO(csv_content), "text/csv")}
    )
    assert response2.status_code == 200
    assert response2.json()["readings_imported"] == 0  # No new readings

    # Still only 1 in database
    readings = db.query(GlucoseReading).all()
    assert len(readings) == 1


def test_upload_cgm_rejects_non_csv(client):
    """Test that non-CSV files are rejected."""
    response = client.post(
        "/api/upload/cgm",
        files={"file": ("data.txt", BytesIO(b"not a csv"), "text/plain")}
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_upload_cgm_empty_csv(client):
    """Test uploading CSV with no glucose data returns error."""
    csv_content = b"""class,value,time,length,photo_url,description,occurred_at,body,updated_at,started_at,ended_at,created_by
StepCountMeasurement,2318,"","","","",2022-12-01 20:59:59 -0800,"","","","",""
"""

    response = client.post(
        "/api/upload/cgm",
        files={"file": ("cgm_data.csv", BytesIO(csv_content), "text/csv")}
    )

    assert response.status_code == 400
    assert "No glucose" in response.json()["detail"]
