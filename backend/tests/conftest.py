"""
Shared pytest fixtures for the Fitbit Dashboard backend test suite.

Provides:
  - db:          An in-memory SQLite session (isolated per test).
  - client:      A FastAPI TestClient wired to the in-memory DB.
  - sample_data: Pre-populated records across all major data types.
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app import models


# ---------------------------------------------------------------------------
# Database fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """Create a fresh in-memory SQLite database for each test.

    Uses ``StaticPool`` so that the same underlying connection is shared
    across threads.  This is critical because FastAPI's ``TestClient``
    dispatches requests in a separate thread, and SQLite in-memory
    databases are per-connection.  Without ``StaticPool`` the worker
    thread would see an empty database without any tables.

    Tables are created before the test and dropped afterward so every
    test starts from a clean state.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db):
    """Return a TestClient whose dependency on ``get_db`` is overridden
    to use the in-memory test database session.
    """

    def _override_get_db():
        try:
            yield db
        finally:
            pass  # session lifecycle managed by the db fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample-data fixture
# ---------------------------------------------------------------------------

_TARGET_DATE = date(2024, 6, 15)
_TARGET_DT = datetime(2024, 6, 15, 10, 30, 0)


@pytest.fixture()
def sample_data(db):
    """Insert one representative record for every major model type.

    Returns a dict mapping short names to the ORM objects that were
    persisted, so tests can assert against known values.
    """
    records = {}

    # Heart Rate Intraday
    hr_intraday = models.HeartRateIntraday(
        timestamp=datetime(2024, 6, 15, 10, 30, 0), bpm=72, confidence=2
    )
    db.add(hr_intraday)
    records["hr_intraday"] = hr_intraday

    hr_intraday_2 = models.HeartRateIntraday(
        timestamp=datetime(2024, 6, 15, 10, 30, 5), bpm=74, confidence=3
    )
    db.add(hr_intraday_2)
    records["hr_intraday_2"] = hr_intraday_2

    # Heart Rate Daily
    hr_daily = models.HeartRateDaily(
        date=_TARGET_DATE,
        resting_heart_rate=62,
        fat_burn_minutes=30,
        cardio_minutes=15,
        peak_minutes=5,
        out_of_range_minutes=180,
    )
    db.add(hr_daily)
    records["hr_daily"] = hr_daily

    # Sleep Log
    sleep = models.SleepLog(
        log_id="sleep_001",
        date=_TARGET_DATE,
        start_time=datetime(2024, 6, 14, 23, 0, 0),
        end_time=datetime(2024, 6, 15, 7, 0, 0),
        duration_ms=28800000,
        efficiency=92,
        minutes_asleep=420,
        minutes_awake=60,
        time_in_bed=480,
        type="stages",
        overall_score=85,
        composition_score=80,
        revitalization_score=78,
        duration_score=90,
        deep_sleep_minutes=90,
        rem_sleep_minutes=100,
        light_sleep_minutes=230,
    )
    db.add(sleep)
    records["sleep"] = sleep

    # Flush to get sleep.id for stages
    db.flush()

    # Sleep Stages
    stage1 = models.SleepStage(
        sleep_log_id=sleep.id,
        timestamp=datetime(2024, 6, 14, 23, 0, 0),
        stage="light",
        duration_seconds=1800,
    )
    stage2 = models.SleepStage(
        sleep_log_id=sleep.id,
        timestamp=datetime(2024, 6, 14, 23, 30, 0),
        stage="deep",
        duration_seconds=3600,
    )
    db.add_all([stage1, stage2])
    records["stage1"] = stage1
    records["stage2"] = stage2

    # SpO2 Daily
    spo2 = models.SpO2Daily(
        date=_TARGET_DATE, avg_spo2=97.2, min_spo2=94.0, max_spo2=99.0
    )
    db.add(spo2)
    records["spo2"] = spo2

    # HRV Daily
    hrv = models.HRVDaily(
        date=_TARGET_DATE, daily_rmssd=42.5, deep_rmssd=55.0
    )
    db.add(hrv)
    records["hrv"] = hrv

    # Breathing Rate
    br = models.BreathingRate(date=_TARGET_DATE, breathing_rate=15.2)
    db.add(br)
    records["br"] = br

    # Skin Temperature
    temp = models.SkinTemperature(date=_TARGET_DATE, relative_temp=-0.3)
    db.add(temp)
    records["temp"] = temp

    # VO2 Max
    vo2 = models.VO2Max(date=_TARGET_DATE, vo2_max=45.0)
    db.add(vo2)
    records["vo2"] = vo2

    # Activity Daily
    activity = models.ActivityDaily(
        date=_TARGET_DATE,
        steps=10500,
        distance_km=8.2,
        floors=12,
        calories_total=2400,
        calories_active=800,
        minutes_sedentary=600,
        minutes_lightly_active=180,
        minutes_fairly_active=45,
        minutes_very_active=30,
        active_zone_minutes=50,
    )
    db.add(activity)
    records["activity"] = activity

    # Activity Intraday
    act_intra = models.ActivityIntraday(
        timestamp=datetime(2024, 6, 15, 8, 0, 0),
        metric="steps",
        value=120.0,
    )
    db.add(act_intra)
    records["act_intra"] = act_intra

    # Stress Score
    stress = models.StressScore(
        date=_TARGET_DATE,
        stress_score=75,
        exertion_score=20,
        responsiveness_score=30,
        sleep_score_component=25,
    )
    db.add(stress)
    records["stress"] = stress

    # Readiness Score
    readiness = models.ReadinessScore(
        date=_TARGET_DATE, readiness_score=82.0
    )
    db.add(readiness)
    records["readiness"] = readiness

    # Exercise
    exercise = models.Exercise(
        log_id="ex_001",
        date=_TARGET_DATE,
        start_time=datetime(2024, 6, 15, 7, 0, 0),
        end_time=datetime(2024, 6, 15, 8, 0, 0),
        activity_name="Run",
        duration_ms=3600000,
        calories=450,
        average_heart_rate=145,
        steps=6000,
        distance_km=5.5,
    )
    db.add(exercise)
    records["exercise"] = exercise

    db.commit()

    # Refresh all objects so their .id attributes are populated
    for obj in records.values():
        db.refresh(obj)

    return records
