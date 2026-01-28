"""
Tests for SQLAlchemy ORM models (app.models).

Covers:
  - Creation of every model type and round-trip read-back.
  - Unique-constraint enforcement (duplicate timestamps / dates).
  - Nullable vs required field enforcement at the DB level.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    """Return (session, engine) backed by an in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


# ======================================================================
# Creation tests -- verify every model can be persisted and read back
# ======================================================================

class TestHeartRateIntradayModel:
    def test_create_and_read(self, db):
        obj = models.HeartRateIntraday(
            timestamp=datetime(2024, 1, 1, 12, 0, 0), bpm=70, confidence=3
        )
        db.add(obj)
        db.commit()

        result = db.query(models.HeartRateIntraday).first()
        assert result is not None
        assert result.bpm == 70
        assert result.confidence == 3
        assert result.timestamp == datetime(2024, 1, 1, 12, 0, 0)

    def test_unique_timestamp(self, db):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        db.add(models.HeartRateIntraday(timestamp=ts, bpm=70))
        db.commit()

        db.add(models.HeartRateIntraday(timestamp=ts, bpm=80))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_nullable_confidence(self, db):
        obj = models.HeartRateIntraday(
            timestamp=datetime(2024, 1, 1, 12, 0, 0), bpm=65
        )
        db.add(obj)
        db.commit()
        result = db.query(models.HeartRateIntraday).first()
        assert result.confidence is None

    def test_bpm_required(self, db):
        obj = models.HeartRateIntraday(timestamp=datetime(2024, 1, 1))
        db.add(obj)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestHeartRateDailyModel:
    def test_create_and_read(self, db):
        obj = models.HeartRateDaily(
            date=date(2024, 1, 1),
            resting_heart_rate=60,
            fat_burn_minutes=20,
            cardio_minutes=10,
            peak_minutes=5,
            out_of_range_minutes=200,
        )
        db.add(obj)
        db.commit()

        result = db.query(models.HeartRateDaily).first()
        assert result.resting_heart_rate == 60
        assert result.date == date(2024, 1, 1)

    def test_unique_date(self, db):
        d = date(2024, 3, 10)
        db.add(models.HeartRateDaily(date=d, resting_heart_rate=60))
        db.commit()

        db.add(models.HeartRateDaily(date=d, resting_heart_rate=62))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_nullable_fields(self, db):
        obj = models.HeartRateDaily(date=date(2024, 1, 1))
        db.add(obj)
        db.commit()
        result = db.query(models.HeartRateDaily).first()
        assert result.resting_heart_rate is None
        assert result.fat_burn_minutes is None


class TestSleepLogModel:
    def test_create_and_read(self, db):
        obj = models.SleepLog(
            log_id="log123",
            date=date(2024, 1, 1),
            start_time=datetime(2023, 12, 31, 23, 0),
            end_time=datetime(2024, 1, 1, 7, 0),
            duration_ms=28800000,
            efficiency=90,
            minutes_asleep=420,
            minutes_awake=60,
            time_in_bed=480,
            type="stages",
        )
        db.add(obj)
        db.commit()
        result = db.query(models.SleepLog).first()
        assert result.log_id == "log123"
        assert result.minutes_asleep == 420

    def test_unique_log_id(self, db):
        db.add(models.SleepLog(
            log_id="dup", date=date(2024, 1, 1),
            start_time=datetime(2024, 1, 1), end_time=datetime(2024, 1, 1, 7),
        ))
        db.commit()

        db.add(models.SleepLog(
            log_id="dup", date=date(2024, 1, 2),
            start_time=datetime(2024, 1, 2), end_time=datetime(2024, 1, 2, 7),
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestSleepStageModel:
    def test_create_and_read(self, db):
        obj = models.SleepStage(
            sleep_log_id=1,
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            stage="deep",
            duration_seconds=1800,
        )
        db.add(obj)
        db.commit()
        result = db.query(models.SleepStage).first()
        assert result.stage == "deep"
        assert result.duration_seconds == 1800

    def test_stage_required(self, db):
        obj = models.SleepStage(
            sleep_log_id=1,
            timestamp=datetime(2024, 1, 1),
        )
        db.add(obj)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestSpO2DailyModel:
    def test_create_and_read(self, db):
        obj = models.SpO2Daily(
            date=date(2024, 1, 1), avg_spo2=97.0, min_spo2=94.0, max_spo2=99.0
        )
        db.add(obj)
        db.commit()
        result = db.query(models.SpO2Daily).first()
        assert result.avg_spo2 == 97.0

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.SpO2Daily(date=d, avg_spo2=97.0))
        db.commit()
        db.add(models.SpO2Daily(date=d, avg_spo2=96.0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestSpO2IntradayModel:
    def test_create_and_read(self, db):
        obj = models.SpO2Intraday(
            timestamp=datetime(2024, 1, 1, 2, 0, 0), spo2=96.5
        )
        db.add(obj)
        db.commit()
        result = db.query(models.SpO2Intraday).first()
        assert result.spo2 == 96.5

    def test_unique_timestamp(self, db):
        ts = datetime(2024, 1, 1, 2, 0, 0)
        db.add(models.SpO2Intraday(timestamp=ts, spo2=96.5))
        db.commit()
        db.add(models.SpO2Intraday(timestamp=ts, spo2=97.0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestHRVDailyModel:
    def test_create_and_read(self, db):
        obj = models.HRVDaily(
            date=date(2024, 1, 1), daily_rmssd=42.5, deep_rmssd=55.0
        )
        db.add(obj)
        db.commit()
        result = db.query(models.HRVDaily).first()
        assert result.daily_rmssd == 42.5
        assert result.deep_rmssd == 55.0

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.HRVDaily(date=d, daily_rmssd=40.0))
        db.commit()
        db.add(models.HRVDaily(date=d, daily_rmssd=45.0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestHRVIntradayModel:
    def test_create_and_read(self, db):
        obj = models.HRVIntraday(
            timestamp=datetime(2024, 1, 1, 2, 0, 0),
            rmssd=35.0,
            coverage=0.95,
            hf=200.0,
            lf=150.0,
        )
        db.add(obj)
        db.commit()
        result = db.query(models.HRVIntraday).first()
        assert result.rmssd == 35.0
        assert result.coverage == 0.95

    def test_unique_timestamp(self, db):
        ts = datetime(2024, 1, 1, 2, 0, 0)
        db.add(models.HRVIntraday(timestamp=ts, rmssd=35.0))
        db.commit()
        db.add(models.HRVIntraday(timestamp=ts, rmssd=40.0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestBreathingRateModel:
    def test_create_and_read(self, db):
        obj = models.BreathingRate(date=date(2024, 1, 1), breathing_rate=15.5)
        db.add(obj)
        db.commit()
        result = db.query(models.BreathingRate).first()
        assert result.breathing_rate == 15.5

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.BreathingRate(date=d, breathing_rate=15.0))
        db.commit()
        db.add(models.BreathingRate(date=d, breathing_rate=16.0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_breathing_rate_required(self, db):
        obj = models.BreathingRate(date=date(2024, 1, 1))
        db.add(obj)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestSkinTemperatureModel:
    def test_create_and_read(self, db):
        obj = models.SkinTemperature(date=date(2024, 1, 1), relative_temp=0.5)
        db.add(obj)
        db.commit()
        result = db.query(models.SkinTemperature).first()
        assert result.relative_temp == 0.5

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.SkinTemperature(date=d, relative_temp=0.5))
        db.commit()
        db.add(models.SkinTemperature(date=d, relative_temp=-0.2))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestVO2MaxModel:
    def test_create_and_read(self, db):
        obj = models.VO2Max(date=date(2024, 1, 1), vo2_max=45.0)
        db.add(obj)
        db.commit()
        result = db.query(models.VO2Max).first()
        assert result.vo2_max == 45.0

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.VO2Max(date=d, vo2_max=45.0))
        db.commit()
        db.add(models.VO2Max(date=d, vo2_max=46.0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_vo2_max_required(self, db):
        obj = models.VO2Max(date=date(2024, 1, 1))
        db.add(obj)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestActivityDailyModel:
    def test_create_and_read(self, db):
        obj = models.ActivityDaily(
            date=date(2024, 1, 1),
            steps=10000,
            distance_km=7.5,
            floors=10,
            calories_total=2200,
            calories_active=700,
        )
        db.add(obj)
        db.commit()
        result = db.query(models.ActivityDaily).first()
        assert result.steps == 10000
        assert result.distance_km == 7.5

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.ActivityDaily(date=d, steps=10000))
        db.commit()
        db.add(models.ActivityDaily(date=d, steps=12000))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestActivityIntradayModel:
    def test_create_and_read(self, db):
        obj = models.ActivityIntraday(
            timestamp=datetime(2024, 1, 1, 8, 0, 0),
            metric="steps",
            value=120.0,
        )
        db.add(obj)
        db.commit()
        result = db.query(models.ActivityIntraday).first()
        assert result.metric == "steps"
        assert result.value == 120.0

    def test_unique_timestamp_metric(self, db):
        ts = datetime(2024, 1, 1, 8, 0, 0)
        db.add(models.ActivityIntraday(timestamp=ts, metric="steps", value=100))
        db.commit()

        db.add(models.ActivityIntraday(timestamp=ts, metric="steps", value=200))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_different_metrics_same_timestamp(self, db):
        ts = datetime(2024, 1, 1, 8, 0, 0)
        db.add(models.ActivityIntraday(timestamp=ts, metric="steps", value=100))
        db.add(models.ActivityIntraday(timestamp=ts, metric="calories", value=5.0))
        db.commit()

        count = db.query(models.ActivityIntraday).count()
        assert count == 2


class TestStressScoreModel:
    def test_create_and_read(self, db):
        obj = models.StressScore(
            date=date(2024, 1, 1),
            stress_score=75,
            exertion_score=20,
            responsiveness_score=30,
        )
        db.add(obj)
        db.commit()
        result = db.query(models.StressScore).first()
        assert result.stress_score == 75

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.StressScore(date=d, stress_score=70))
        db.commit()
        db.add(models.StressScore(date=d, stress_score=80))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_stress_score_required(self, db):
        obj = models.StressScore(date=date(2024, 1, 1))
        db.add(obj)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestReadinessScoreModel:
    def test_create_and_read(self, db):
        obj = models.ReadinessScore(date=date(2024, 1, 1), readiness_score=80.0)
        db.add(obj)
        db.commit()
        result = db.query(models.ReadinessScore).first()
        assert result.readiness_score == 80.0

    def test_unique_date(self, db):
        d = date(2024, 1, 1)
        db.add(models.ReadinessScore(date=d, readiness_score=80.0))
        db.commit()
        db.add(models.ReadinessScore(date=d, readiness_score=85.0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestExerciseModel:
    def test_create_and_read(self, db):
        obj = models.Exercise(
            log_id="ex_100",
            date=date(2024, 1, 1),
            start_time=datetime(2024, 1, 1, 7, 0),
            end_time=datetime(2024, 1, 1, 8, 0),
            activity_name="Run",
            duration_ms=3600000,
            calories=450,
            average_heart_rate=145,
            steps=6000,
            distance_km=5.5,
        )
        db.add(obj)
        db.commit()
        result = db.query(models.Exercise).first()
        assert result.activity_name == "Run"
        assert result.calories == 450

    def test_unique_log_id(self, db):
        db.add(models.Exercise(
            log_id="dup_ex", date=date(2024, 1, 1),
            start_time=datetime(2024, 1, 1, 7), activity_name="Walk",
        ))
        db.commit()
        db.add(models.Exercise(
            log_id="dup_ex", date=date(2024, 1, 2),
            start_time=datetime(2024, 1, 2, 7), activity_name="Run",
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_activity_name_required(self, db):
        obj = models.Exercise(
            date=date(2024, 1, 1),
            start_time=datetime(2024, 1, 1, 7),
        )
        db.add(obj)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestSyncStatusModel:
    def test_create_and_read(self, db):
        obj = models.SyncStatus(
            data_type="heart_rate",
            last_synced=datetime(2024, 1, 1, 12, 0, 0),
        )
        db.add(obj)
        db.commit()
        result = db.query(models.SyncStatus).first()
        assert result.data_type == "heart_rate"

    def test_unique_data_type(self, db):
        db.add(models.SyncStatus(
            data_type="heart_rate", last_synced=datetime(2024, 1, 1)
        ))
        db.commit()
        db.add(models.SyncStatus(
            data_type="heart_rate", last_synced=datetime(2024, 1, 2)
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestOAuthTokenModel:
    def test_create_and_read(self, db):
        obj = models.OAuthToken(
            access_token="access_abc",
            refresh_token="refresh_xyz",
            token_type="Bearer",
            expires_at=1700000000.0,
            scope="activity heartrate",
            user_id="USER123",
        )
        db.add(obj)
        db.commit()
        result = db.query(models.OAuthToken).first()
        assert result.access_token == "access_abc"
        assert result.user_id == "USER123"
