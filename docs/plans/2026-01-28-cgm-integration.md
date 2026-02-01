# CGM Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add CGM (Continuous Glucose Monitor) data visualization with CSV import, LibreLinkUp live sync, and correlation with Fitbit metrics.

**Architecture:** New GlucoseReading model stores per-reading data. CSV parser handles historical imports. LibreLinkUp service polls for live data. Frontend adds Glucose page with timeline, time-in-range, and AGP charts. Glucose metrics added to correlations.

**Tech Stack:** Python/FastAPI, SQLAlchemy, React/TypeScript, Recharts, libre-link-up-api-client pattern

---

## Task 1: Database Model

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/tests/test_glucose_model.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_glucose_model.py
import pytest
from datetime import datetime
from app.models import GlucoseReading
from app.database import get_db

def test_glucose_reading_model(db_session):
    reading = GlucoseReading(
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        value=95,
        source="csv_import"
    )
    db_session.add(reading)
    db_session.commit()

    result = db_session.query(GlucoseReading).first()
    assert result.value == 95
    assert result.source == "csv_import"
    assert result.timestamp.hour == 10
```

**Step 2: Run test to verify it fails**

```bash
cd backend && source venv/bin/activate && pytest tests/test_glucose_model.py -v
```
Expected: FAIL with "cannot import name 'GlucoseReading'"

**Step 3: Add the model**

```python
# In backend/app/models.py, add after other models:

class GlucoseReading(Base):
    __tablename__ = "glucose_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    value = Column(Integer, nullable=False)  # mg/dL
    source = Column(String(50))  # "csv_import", "librelinkup", "manual"

    __table_args__ = (
        Index('ix_glucose_timestamp_source', 'timestamp', 'source'),
    )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_glucose_model.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_glucose_model.py
git commit -m "feat(models): add GlucoseReading model for CGM data"
```

---

## Task 2: CSV Parser for CGM Import

**Files:**
- Modify: `backend/app/parsers/export_parser.py`
- Create: `backend/tests/test_cgm_parser.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_cgm_parser.py
import pytest
from io import StringIO
from datetime import datetime
from app.parsers.export_parser import parse_cgm_csv

def test_parse_cgm_csv():
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cgm_parser.py -v
```
Expected: FAIL with "cannot import name 'parse_cgm_csv'"

**Step 3: Implement the parser**

```python
# In backend/app/parsers/export_parser.py, add:

import csv
from datetime import datetime
from typing import List, Dict, Any, TextIO
import re

def parse_cgm_csv(file: TextIO) -> List[Dict[str, Any]]:
    """Parse CGM data from health export CSV format."""
    readings = []
    reader = csv.DictReader(file)

    for row in reader:
        if row.get("class") != "GlucoseMeasurement":
            continue

        try:
            value = int(float(row["value"]))
            occurred_at = row["occurred_at"]

            # Parse timestamp like "2022-12-01 19:14:27 -0800"
            # Remove timezone offset for naive datetime
            match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", occurred_at)
            if not match:
                continue
            timestamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")

            readings.append({
                "timestamp": timestamp,
                "value": value,
                "source": "csv_import"
            })
        except (ValueError, KeyError):
            continue

    return readings
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cgm_parser.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/parsers/export_parser.py backend/tests/test_cgm_parser.py
git commit -m "feat(parser): add CGM CSV parser for glucose measurements"
```

---

## Task 3: CGM Upload Endpoint

**Files:**
- Modify: `backend/app/routers/upload.py`
- Create: `backend/tests/test_cgm_upload.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_cgm_upload.py
import pytest
from fastapi.testclient import TestClient
from io import BytesIO

def test_upload_cgm_csv(client: TestClient, db_session):
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_cgm_upload.py -v
```
Expected: FAIL with 404 Not Found

**Step 3: Add the endpoint**

```python
# In backend/app/routers/upload.py, add:

from app.parsers.export_parser import parse_cgm_csv
from app.models import GlucoseReading
from io import StringIO

@router.post("/cgm")
async def upload_cgm(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload CGM data from CSV export."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    text = content.decode("utf-8")

    readings = parse_cgm_csv(StringIO(text))

    if not readings:
        raise HTTPException(status_code=400, detail="No glucose measurements found in file")

    # Upsert readings (avoid duplicates by timestamp)
    imported = 0
    for r in readings:
        existing = db.query(GlucoseReading).filter(
            GlucoseReading.timestamp == r["timestamp"]
        ).first()

        if not existing:
            db.add(GlucoseReading(**r))
            imported += 1

    db.commit()

    return {
        "readings_imported": imported,
        "total_in_file": len(readings),
        "source": "csv_import"
    }
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_cgm_upload.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/routers/upload.py backend/tests/test_cgm_upload.py
git commit -m "feat(api): add CGM CSV upload endpoint"
```

---

## Task 4: Glucose Data Endpoints

**Files:**
- Modify: `backend/app/routers/data.py`
- Create: `backend/tests/test_glucose_api.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_glucose_api.py
import pytest
from datetime import datetime, date
from fastapi.testclient import TestClient
from app.models import GlucoseReading

def test_get_glucose_readings(client: TestClient, db_session):
    # Add test data
    readings = [
        GlucoseReading(timestamp=datetime(2024, 1, 15, 10, 0), value=90, source="test"),
        GlucoseReading(timestamp=datetime(2024, 1, 15, 10, 15), value=95, source="test"),
        GlucoseReading(timestamp=datetime(2024, 1, 15, 10, 30), value=110, source="test"),
    ]
    for r in readings:
        db_session.add(r)
    db_session.commit()

    response = client.get("/api/data/glucose?date=2024-01-15")
    assert response.status_code == 200
    data = response.json()
    assert len(data["readings"]) == 3
    assert data["readings"][0]["value"] == 90

def test_get_glucose_daily_summary(client: TestClient, db_session):
    # Add readings for calculating daily stats
    readings = [
        GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=70, source="test"),
        GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"),
        GlucoseReading(timestamp=datetime(2024, 1, 15, 18, 0), value=150, source="test"),
        GlucoseReading(timestamp=datetime(2024, 1, 15, 22, 0), value=80, source="test"),
    ]
    for r in readings:
        db_session.add(r)
    db_session.commit()

    response = client.get("/api/data/glucose/daily?start=2024-01-15&end=2024-01-15")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["avg"] == 100  # (70+100+150+80)/4
    assert data[0]["min"] == 70
    assert data[0]["max"] == 150

def test_get_glucose_time_in_range(client: TestClient, db_session):
    # 4 readings: 1 low (<70), 2 in range (70-180), 1 high (>180)
    readings = [
        GlucoseReading(timestamp=datetime(2024, 1, 15, 8, 0), value=60, source="test"),  # low
        GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"),  # in range
        GlucoseReading(timestamp=datetime(2024, 1, 15, 16, 0), value=120, source="test"),  # in range
        GlucoseReading(timestamp=datetime(2024, 1, 15, 20, 0), value=200, source="test"),  # high
    ]
    for r in readings:
        db_session.add(r)
    db_session.commit()

    response = client.get("/api/data/glucose/time-in-range?start=2024-01-15&end=2024-01-15")
    assert response.status_code == 200
    data = response.json()
    assert data["in_range_percent"] == 50.0
    assert data["low_percent"] == 25.0
    assert data["high_percent"] == 25.0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_glucose_api.py -v
```
Expected: FAIL with 404

**Step 3: Implement the endpoints**

```python
# In backend/app/routers/data.py, add these endpoints:

from app.models import GlucoseReading
from sqlalchemy import func

@router.get("/glucose")
def get_glucose_readings(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """Get glucose readings for a specific day."""
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

    readings = db.query(GlucoseReading).filter(
        GlucoseReading.timestamp >= start_dt,
        GlucoseReading.timestamp < end_dt
    ).order_by(GlucoseReading.timestamp).all()

    return {
        "date": date,
        "readings": [
            {
                "timestamp": r.timestamp.isoformat(),
                "value": r.value,
                "source": r.source
            }
            for r in readings
        ]
    }


@router.get("/glucose/daily")
def get_glucose_daily(
    start: str = Query(None),
    end: str = Query(None),
    db: Session = Depends(get_db)
):
    """Get daily glucose summaries."""
    start_date, end_date = _date_range(start, end)
    start_dt, end_dt = _dt_range(start_date, end_date)

    # Query with date grouping
    results = db.query(
        func.date(GlucoseReading.timestamp).label("date"),
        func.avg(GlucoseReading.value).label("avg"),
        func.min(GlucoseReading.value).label("min"),
        func.max(GlucoseReading.value).label("max"),
        func.count(GlucoseReading.id).label("count")
    ).filter(
        GlucoseReading.timestamp >= start_dt,
        GlucoseReading.timestamp < end_dt
    ).group_by(
        func.date(GlucoseReading.timestamp)
    ).order_by(
        func.date(GlucoseReading.timestamp)
    ).all()

    return [
        {
            "date": str(r.date),
            "avg": round(r.avg),
            "min": r.min,
            "max": r.max,
            "count": r.count
        }
        for r in results
    ]


@router.get("/glucose/time-in-range")
def get_glucose_time_in_range(
    start: str = Query(None),
    end: str = Query(None),
    low_threshold: int = Query(70),
    high_threshold: int = Query(180),
    db: Session = Depends(get_db)
):
    """Calculate time in range statistics."""
    start_date, end_date = _date_range(start, end)
    start_dt, end_dt = _dt_range(start_date, end_date)

    readings = db.query(GlucoseReading.value).filter(
        GlucoseReading.timestamp >= start_dt,
        GlucoseReading.timestamp < end_dt
    ).all()

    if not readings:
        return {
            "total_readings": 0,
            "in_range_percent": 0,
            "low_percent": 0,
            "high_percent": 0,
            "very_low_percent": 0,
            "very_high_percent": 0
        }

    total = len(readings)
    low = sum(1 for r in readings if r.value < low_threshold)
    high = sum(1 for r in readings if r.value > high_threshold)
    very_low = sum(1 for r in readings if r.value < 54)
    very_high = sum(1 for r in readings if r.value > 250)
    in_range = total - low - high

    return {
        "total_readings": total,
        "in_range_percent": round(in_range / total * 100, 1),
        "low_percent": round(low / total * 100, 1),
        "high_percent": round(high / total * 100, 1),
        "very_low_percent": round(very_low / total * 100, 1),
        "very_high_percent": round(very_high / total * 100, 1)
    }
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_glucose_api.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/routers/data.py backend/tests/test_glucose_api.py
git commit -m "feat(api): add glucose data endpoints"
```

---

## Task 5: AGP (Ambulatory Glucose Profile) Endpoint

**Files:**
- Modify: `backend/app/routers/data.py`
- Add test to: `backend/tests/test_glucose_api.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_glucose_api.py

def test_get_glucose_agp(client: TestClient, db_session):
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
        db_session.add(r)
    db_session.commit()

    response = client.get("/api/data/glucose/agp?start=2024-01-15&end=2024-01-16")
    assert response.status_code == 200
    data = response.json()

    # Should have 24 hourly buckets
    assert len(data["hourly"]) == 24

    # Check 8am bucket (hour 8)
    hour_8 = next(h for h in data["hourly"] if h["hour"] == 8)
    assert hour_8["median"] == 85  # median of [80, 90]
    assert hour_8["p10"] <= hour_8["p25"] <= hour_8["median"] <= hour_8["p75"] <= hour_8["p90"]
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_glucose_api.py::test_get_glucose_agp -v
```
Expected: FAIL with 404

**Step 3: Implement AGP endpoint**

```python
# Add to backend/app/routers/data.py

import numpy as np

@router.get("/glucose/agp")
def get_glucose_agp(
    start: str = Query(None),
    end: str = Query(None),
    db: Session = Depends(get_db)
):
    """Calculate Ambulatory Glucose Profile (percentiles by hour of day)."""
    start_date, end_date = _date_range(start, end)
    # Default to 14 days for AGP
    if start is None:
        start_date = end_date - timedelta(days=14)

    start_dt, end_dt = _dt_range(start_date, end_date)

    readings = db.query(
        GlucoseReading.timestamp,
        GlucoseReading.value
    ).filter(
        GlucoseReading.timestamp >= start_dt,
        GlucoseReading.timestamp < end_dt
    ).all()

    # Group by hour of day
    hourly_values: dict = {h: [] for h in range(24)}
    for r in readings:
        hour = r.timestamp.hour
        hourly_values[hour].append(r.value)

    hourly_stats = []
    for hour in range(24):
        values = hourly_values[hour]
        if not values:
            hourly_stats.append({
                "hour": hour,
                "p10": None, "p25": None, "median": None, "p75": None, "p90": None, "count": 0
            })
        else:
            arr = np.array(values)
            hourly_stats.append({
                "hour": hour,
                "p10": int(np.percentile(arr, 10)),
                "p25": int(np.percentile(arr, 25)),
                "median": int(np.percentile(arr, 50)),
                "p75": int(np.percentile(arr, 75)),
                "p90": int(np.percentile(arr, 90)),
                "count": len(values)
            })

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "total_readings": len(readings),
        "hourly": hourly_stats
    }
```

**Step 4: Add numpy dependency**

```bash
pip install numpy && pip freeze | grep numpy >> requirements.txt
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_glucose_api.py::test_get_glucose_agp -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/routers/data.py backend/tests/test_glucose_api.py backend/requirements.txt
git commit -m "feat(api): add AGP endpoint for glucose percentile analysis"
```

---

## Task 6: Add Glucose to Correlations

**Files:**
- Modify: `backend/app/routers/data.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_glucose_api.py

def test_correlations_with_glucose(client: TestClient, db_session):
    """Test that glucose can be correlated with other metrics."""
    from app.models import HeartRateDaily

    # Add glucose and heart rate for same dates
    db_session.add(GlucoseReading(timestamp=datetime(2024, 1, 15, 12, 0), value=100, source="test"))
    db_session.add(GlucoseReading(timestamp=datetime(2024, 1, 16, 12, 0), value=110, source="test"))
    db_session.add(HeartRateDaily(date=date(2024, 1, 15), resting_hr=60))
    db_session.add(HeartRateDaily(date=date(2024, 1, 16), resting_hr=65))
    db_session.commit()

    response = client.get("/api/data/correlations?x=avg_glucose&y=resting_hr&start=2024-01-15&end=2024-01-16")
    assert response.status_code == 200
    data = response.json()
    assert len(data["points"]) == 2
    assert "avg_glucose" in data["availableMetrics"]
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_glucose_api.py::test_correlations_with_glucose -v
```
Expected: FAIL

**Step 3: Update correlations to include glucose**

In `backend/app/routers/data.py`, update the `get_correlations` function to:

1. Add `"avg_glucose"` to the `METRIC_SOURCES` dict:
```python
METRIC_SOURCES = {
    # ... existing metrics ...
    "avg_glucose": (GlucoseReading, "date", "value"),  # We'll aggregate daily
}
```

2. Add special handling for glucose (since it needs daily aggregation):
```python
# In get_correlations, before the main query logic:
if x_metric == "avg_glucose" or y_metric == "avg_glucose":
    # Get daily glucose averages
    glucose_daily = db.query(
        func.date(GlucoseReading.timestamp).label("date"),
        func.avg(GlucoseReading.value).label("avg")
    ).filter(
        GlucoseReading.timestamp >= start_dt,
        GlucoseReading.timestamp < end_dt
    ).group_by(func.date(GlucoseReading.timestamp)).all()

    glucose_by_date = {str(g.date): round(g.avg) for g in glucose_daily}
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_glucose_api.py::test_correlations_with_glucose -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/routers/data.py backend/tests/test_glucose_api.py
git commit -m "feat(api): add glucose to correlation analysis"
```

---

## Task 7: Update Correlations Default Date Range

**Files:**
- Modify: `backend/app/routers/data.py`
- Modify: `frontend/src/pages/Correlations.tsx`

**Step 1: Update backend to use full date range**

In `backend/app/routers/data.py`, modify the `_date_range` helper:

```python
def _date_range(start: str | None, end: str | None, db: Session = None):
    """Parse date range, defaulting to all available data if db provided."""
    end_date = date.fromisoformat(end) if end else date.today()

    if start:
        start_date = date.fromisoformat(start)
    elif db:
        # Find earliest data date from key tables
        earliest = None
        for model in [HeartRateDaily, SleepLog, GlucoseReading]:
            # ... find min date
        start_date = earliest or end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=90)

    return start_date, end_date
```

**Step 2: Update frontend**

In `frontend/src/pages/Correlations.tsx`, add "All Time" preset to DateRangePicker:

```typescript
// Replace hardcoded 90 days with fetching from /api/metrics
useEffect(() => {
  fetch(`${API_BASE}/api/metrics`)
    .then(res => res.json())
    .then(data => {
      // Find earliest date across all metrics
      const dates = Object.values(data)
        .flatMap((m: any) => [m.first_date, m.last_date])
        .filter(Boolean);
      if (dates.length) {
        setStartDate(dates.sort()[0]);
      }
    });
}, []);
```

**Step 3: Commit**

```bash
git add backend/app/routers/data.py frontend/src/pages/Correlations.tsx
git commit -m "feat: default correlations to all available data"
```

---

## Task 8: Frontend Glucose Page - Timeline Chart

**Files:**
- Create: `frontend/src/pages/Glucose.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create basic Glucose page with timeline**

```typescript
// frontend/src/pages/Glucose.tsx
import { useState, useEffect } from "react";
import { format, subDays } from "date-fns";
import { Droplet } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, ReferenceArea
} from "recharts";
import DateRangePicker from "../components/DateRangePicker";

const API_BASE = "http://localhost:8000";

interface GlucoseReading {
  timestamp: string;
  value: number;
}

export default function Glucose() {
  const [date, setDate] = useState(format(new Date(), "yyyy-MM-dd"));
  const [readings, setReadings] = useState<GlucoseReading[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/data/glucose?date=${date}`)
      .then(res => res.json())
      .then(data => {
        setReadings(data.readings || []);
      })
      .finally(() => setLoading(false));
  }, [date]);

  const chartData = readings.map(r => ({
    time: format(new Date(r.timestamp), "HH:mm"),
    value: r.value
  }));

  return (
    <div className="page">
      <div className="page-header">
        <Droplet size={24} />
        <h2>Glucose</h2>
      </div>

      <DateRangePicker
        startDate={date}
        endDate={date}
        onChange={(start) => setDate(start)}
      />

      <div className="card">
        <div className="card-header">
          <h3>Daily Timeline</h3>
        </div>

        {loading ? (
          <p>Loading...</p>
        ) : readings.length === 0 ? (
          <p className="text-muted">No glucose data for this date</p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              {/* Target range background */}
              <ReferenceArea y1={70} y2={180} fill="var(--success)" fillOpacity={0.1} />
              <ReferenceLine y={70} stroke="var(--warning)" strokeDasharray="3 3" />
              <ReferenceLine y={180} stroke="var(--warning)" strokeDasharray="3 3" />

              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis domain={[40, 250]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Add route and nav link**

In `App.tsx`, add:
```typescript
import Glucose from "./pages/Glucose";
// In routes:
<Route path="/glucose" element={<Glucose />} />
```

In `Layout.tsx`, add nav item:
```typescript
{ path: "/glucose", label: "Glucose", icon: Droplet }
```

**Step 3: Test manually and commit**

```bash
npm run dev
# Open http://localhost:5173/glucose
```

```bash
git add frontend/src/pages/Glucose.tsx frontend/src/components/Layout.tsx frontend/src/App.tsx
git commit -m "feat(ui): add Glucose page with daily timeline chart"
```

---

## Task 9: Frontend - Time in Range Component

**Files:**
- Modify: `frontend/src/pages/Glucose.tsx`

**Step 1: Add time-in-range stats card**

```typescript
// Add to Glucose.tsx

interface TimeInRange {
  total_readings: number;
  in_range_percent: number;
  low_percent: number;
  high_percent: number;
  very_low_percent: number;
  very_high_percent: number;
}

// In component, add state and fetch:
const [tir, setTir] = useState<TimeInRange | null>(null);

useEffect(() => {
  fetch(`${API_BASE}/api/data/glucose/time-in-range?start=${startDate}&end=${endDate}`)
    .then(res => res.json())
    .then(setTir);
}, [startDate, endDate]);

// Add card to render:
{tir && (
  <div className="card">
    <div className="card-header">
      <h3>Time in Range</h3>
    </div>
    <div style={{ display: "flex", gap: 20, justifyContent: "center" }}>
      <div className="stat-box" style={{ color: "var(--success)" }}>
        <span className="stat-value">{tir.in_range_percent}%</span>
        <span className="stat-label">In Range (70-180)</span>
      </div>
      <div className="stat-box" style={{ color: "var(--warning)" }}>
        <span className="stat-value">{tir.low_percent}%</span>
        <span className="stat-label">Low (&lt;70)</span>
      </div>
      <div className="stat-box" style={{ color: "var(--danger)" }}>
        <span className="stat-value">{tir.high_percent}%</span>
        <span className="stat-label">High (&gt;180)</span>
      </div>
    </div>
  </div>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Glucose.tsx
git commit -m "feat(ui): add time-in-range stats to Glucose page"
```

---

## Task 10: Frontend - AGP Chart

**Files:**
- Modify: `frontend/src/pages/Glucose.tsx`

**Step 1: Add AGP visualization**

```typescript
// Add AGP chart showing percentile bands
interface AGPData {
  hourly: Array<{
    hour: number;
    p10: number | null;
    p25: number | null;
    median: number | null;
    p75: number | null;
    p90: number | null;
  }>;
}

// Fetch and render as area chart with percentile bands:
<AreaChart data={agp.hourly}>
  <Area type="monotone" dataKey="p90" stackId="1" fill="var(--warning)" fillOpacity={0.2} />
  <Area type="monotone" dataKey="p75" stackId="2" fill="var(--accent)" fillOpacity={0.3} />
  <Line type="monotone" dataKey="median" stroke="var(--accent)" strokeWidth={2} />
  <Area type="monotone" dataKey="p25" stackId="3" fill="var(--accent)" fillOpacity={0.3} />
  <Area type="monotone" dataKey="p10" stackId="4" fill="var(--warning)" fillOpacity={0.2} />
</AreaChart>
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Glucose.tsx
git commit -m "feat(ui): add AGP chart with percentile bands"
```

---

## Task 11: Settings - CGM Upload

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

**Step 1: Add CGM upload section**

```typescript
// Add to Settings.tsx

const [cgmUploading, setCgmUploading] = useState(false);
const [cgmResult, setCgmResult] = useState<string | null>(null);

const handleCgmUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;

  setCgmUploading(true);
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/upload/cgm`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    setCgmResult(`Imported ${data.readings_imported} glucose readings`);
  } catch (err) {
    setCgmResult("Upload failed");
  } finally {
    setCgmUploading(false);
  }
};

// Add card in render:
<div className="card">
  <div className="card-header">
    <h3>CGM Data Import</h3>
  </div>
  <p>Upload your CGM export CSV file to import glucose data.</p>
  <input type="file" accept=".csv" onChange={handleCgmUpload} disabled={cgmUploading} />
  {cgmResult && <p className="status-message success">{cgmResult}</p>}
</div>
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat(ui): add CGM upload to Settings page"
```

---

## Task 12: LibreLinkUp Integration (Backend)

**Files:**
- Create: `backend/app/services/librelinkup.py`
- Create: `backend/tests/test_librelinkup.py`
- Modify: `backend/app/routers/data.py`

**Step 1: Create LibreLinkUp service**

```python
# backend/app/services/librelinkup.py
import httpx
from datetime import datetime
from typing import List, Dict, Optional

LIBRE_API_BASE = "https://api.libreview.io"

class LibreLinkUpClient:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.token: Optional[str] = None
        self.patient_id: Optional[str] = None

    async def login(self) -> bool:
        """Authenticate with LibreView API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LIBRE_API_BASE}/llu/auth/login",
                json={"email": self.email, "password": self.password},
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("data", {}).get("authTicket", {}).get("token")
                return True
        return False

    async def get_connections(self) -> List[Dict]:
        """Get connected patients/users."""
        if not self.token:
            await self.login()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LIBRE_API_BASE}/llu/connections",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if response.status_code == 200:
                return response.json().get("data", [])
        return []

    async def get_readings(self, patient_id: str) -> List[Dict]:
        """Fetch glucose readings for a patient."""
        if not self.token:
            await self.login()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LIBRE_API_BASE}/llu/connections/{patient_id}/graph",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if response.status_code == 200:
                data = response.json().get("data", {})
                readings = data.get("graphData", [])
                return [
                    {
                        "timestamp": datetime.fromisoformat(r["Timestamp"].replace("Z", "+00:00")),
                        "value": r["Value"],
                        "source": "librelinkup"
                    }
                    for r in readings
                ]
        return []
```

**Step 2: Add sync endpoint**

```python
# In backend/app/routers/data.py or create new router

@router.post("/sync/cgm")
async def sync_cgm(
    email: str = Query(...),
    password: str = Query(...),
    db: Session = Depends(get_db)
):
    """Sync glucose data from LibreLinkUp."""
    from app.services.librelinkup import LibreLinkUpClient

    client = LibreLinkUpClient(email, password)
    if not await client.login():
        raise HTTPException(401, "Failed to authenticate with LibreLinkUp")

    connections = await client.get_connections()
    if not connections:
        raise HTTPException(404, "No connections found")

    # Get readings for first connection
    readings = await client.get_readings(connections[0]["patientId"])

    imported = 0
    for r in readings:
        existing = db.query(GlucoseReading).filter(
            GlucoseReading.timestamp == r["timestamp"]
        ).first()
        if not existing:
            db.add(GlucoseReading(**r))
            imported += 1

    db.commit()

    return {"readings_imported": imported}
```

**Step 3: Commit**

```bash
pip install httpx && pip freeze | grep httpx >> requirements.txt
git add backend/app/services/librelinkup.py backend/app/routers/data.py backend/requirements.txt
git commit -m "feat(sync): add LibreLinkUp integration for live CGM sync"
```

---

## Task 13: Frontend Correlations - Add Glucose Metrics

**Files:**
- Modify: `frontend/src/pages/Correlations.tsx`

**Step 1: Add glucose to metric options**

```typescript
// Add to METRIC_LABELS:
avg_glucose: "Average Glucose (mg/dL)",

// Add suggested pair:
{ label: "Glucose vs Sleep Score", x: "avg_glucose", y: "sleep_score" },
{ label: "Glucose vs Resting HR", x: "avg_glucose", y: "resting_hr" },
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Correlations.tsx
git commit -m "feat(ui): add glucose to correlation metrics"
```

---

## Task 14: Run All Tests

**Step 1: Backend tests**

```bash
cd backend && source venv/bin/activate && pytest -v
```

**Step 2: Frontend tests**

```bash
cd frontend && npm test
```

**Step 3: Fix any failures and commit**

```bash
git add -A
git commit -m "test: ensure all tests pass after CGM integration"
```

---

## Task 15: Import Existing CGM Data

**Step 1: Start the servers**

```bash
# Terminal 1
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

**Step 2: Import the CSV**

Go to http://localhost:5173/settings and upload `data/past cgm data-export.csv`

**Step 3: Verify**

Go to http://localhost:5173/glucose and check that data displays correctly.

---

## Summary

This plan adds:
- **Database**: GlucoseReading model
- **Parsers**: CSV import for health export format
- **API**: 5 new endpoints (glucose, daily, time-in-range, AGP, correlations)
- **Sync**: LibreLinkUp integration for live data
- **Frontend**: Glucose page with 3 visualizations
- **Settings**: CGM upload section
- **Correlations**: Glucose as available metric

After completing all tasks, run the full test suite and push to GitHub.
