from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Date, Boolean, Text, Index
)
from app.database import Base


class HeartRateIntraday(Base):
    """Per-second or per-5-second heart rate readings."""
    __tablename__ = "heart_rate_intraday"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    bpm = Column(Integer, nullable=False)
    confidence = Column(Integer, nullable=True)  # from export data

    __table_args__ = (
        Index("ix_hr_intraday_ts", "timestamp", unique=True),
    )


class HeartRateDaily(Base):
    """Daily heart rate summary: resting HR + zone minutes."""
    __tablename__ = "heart_rate_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    resting_heart_rate = Column(Integer, nullable=True)
    fat_burn_minutes = Column(Integer, nullable=True)
    cardio_minutes = Column(Integer, nullable=True)
    peak_minutes = Column(Integer, nullable=True)
    out_of_range_minutes = Column(Integer, nullable=True)


class SleepLog(Base):
    """One row per sleep session."""
    __tablename__ = "sleep_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_id = Column(String, nullable=True, unique=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    efficiency = Column(Integer, nullable=True)
    minutes_asleep = Column(Integer, nullable=True)
    minutes_awake = Column(Integer, nullable=True)
    time_in_bed = Column(Integer, nullable=True)
    type = Column(String, nullable=True)  # "stages" or "classic"

    # Sleep score components
    overall_score = Column(Integer, nullable=True)
    composition_score = Column(Integer, nullable=True)
    revitalization_score = Column(Integer, nullable=True)
    duration_score = Column(Integer, nullable=True)
    deep_sleep_minutes = Column(Integer, nullable=True)
    rem_sleep_minutes = Column(Integer, nullable=True)
    light_sleep_minutes = Column(Integer, nullable=True)


class SleepStage(Base):
    """Per-30-second sleep stage readings within a sleep session."""
    __tablename__ = "sleep_stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sleep_log_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    stage = Column(String, nullable=False)  # wake, light, deep, rem
    duration_seconds = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_sleep_stage_log_ts", "sleep_log_id", "timestamp"),
    )


class SpO2Daily(Base):
    """Nightly SpO2 summary."""
    __tablename__ = "spo2_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    avg_spo2 = Column(Float, nullable=True)
    min_spo2 = Column(Float, nullable=True)
    max_spo2 = Column(Float, nullable=True)


class SpO2Intraday(Base):
    """Intraday SpO2 readings during sleep."""
    __tablename__ = "spo2_intraday"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    spo2 = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_spo2_intraday_ts", "timestamp", unique=True),
    )


class HRVDaily(Base):
    """Nightly HRV summary."""
    __tablename__ = "hrv_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    daily_rmssd = Column(Float, nullable=True)
    deep_rmssd = Column(Float, nullable=True)


class HRVIntraday(Base):
    """Intraday HRV readings (5-minute intervals during sleep)."""
    __tablename__ = "hrv_intraday"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    rmssd = Column(Float, nullable=False)
    coverage = Column(Float, nullable=True)
    hf = Column(Float, nullable=True)  # high frequency power
    lf = Column(Float, nullable=True)  # low frequency power

    __table_args__ = (
        Index("ix_hrv_intraday_ts", "timestamp", unique=True),
    )


class BreathingRate(Base):
    """Nightly breathing rate."""
    __tablename__ = "breathing_rate"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    breathing_rate = Column(Float, nullable=False)


class SkinTemperature(Base):
    """Nightly skin temperature variation from baseline."""
    __tablename__ = "skin_temperature"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    relative_temp = Column(Float, nullable=False)  # deviation from baseline


class VO2Max(Base):
    """Estimated VO2 Max (cardio fitness score)."""
    __tablename__ = "vo2_max"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    vo2_max = Column(Float, nullable=False)


class ActivityDaily(Base):
    """Daily activity summary."""
    __tablename__ = "activity_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    steps = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    floors = Column(Integer, nullable=True)
    calories_total = Column(Integer, nullable=True)
    calories_active = Column(Integer, nullable=True)
    minutes_sedentary = Column(Integer, nullable=True)
    minutes_lightly_active = Column(Integer, nullable=True)
    minutes_fairly_active = Column(Integer, nullable=True)
    minutes_very_active = Column(Integer, nullable=True)
    active_zone_minutes = Column(Integer, nullable=True)


class ActivityIntraday(Base):
    """Per-minute activity data (steps, calories, distance)."""
    __tablename__ = "activity_intraday"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    metric = Column(String, nullable=False)  # steps, calories, distance
    value = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_activity_intraday_ts_metric", "timestamp", "metric", unique=True),
    )


class StressScore(Base):
    """Daily stress management score."""
    __tablename__ = "stress_score"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    stress_score = Column(Integer, nullable=False)
    exertion_score = Column(Integer, nullable=True)
    responsiveness_score = Column(Integer, nullable=True)
    sleep_score_component = Column(Integer, nullable=True)


class ReadinessScore(Base):
    """Daily readiness score (Premium)."""
    __tablename__ = "readiness_score"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    readiness_score = Column(Float, nullable=False)


class Exercise(Base):
    """Logged exercise sessions."""
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_id = Column(String, nullable=True, unique=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    activity_name = Column(String, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    calories = Column(Integer, nullable=True)
    average_heart_rate = Column(Integer, nullable=True)
    steps = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)


class SyncStatus(Base):
    """Tracks last successful sync per data type."""
    __tablename__ = "sync_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_type = Column(String, nullable=False, unique=True)
    last_synced = Column(DateTime, nullable=False)


class OAuthToken(Base):
    """Stores Fitbit OAuth2 tokens."""
    __tablename__ = "oauth_token"

    id = Column(Integer, primary_key=True, autoincrement=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_type = Column(String, nullable=True)
    expires_at = Column(Float, nullable=False)
    scope = Column(Text, nullable=True)
    user_id = Column(String, nullable=True)
