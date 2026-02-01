from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db
from app import models

router = APIRouter(tags=["data"])


# ─── Helper ───────────────────────────────────────────────────

def _date_range(start: Optional[str], end: Optional[str]):
    """Parse start/end query params, defaulting to last 7 days."""
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=7)
    return start_date, end_date


def _dt_range(start_date: date, end_date: date):
    """Convert date range to datetime range for intraday queries."""
    return datetime.combine(start_date, datetime.min.time()), \
           datetime.combine(end_date + timedelta(days=1), datetime.min.time())


# ─── Metrics Info ─────────────────────────────────────────────

@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """List all available metrics with their date ranges."""
    metrics = []

    metric_configs = [
        ("heart_rate_intraday", "Heart Rate (Intraday)", "bpm", models.HeartRateIntraday, "timestamp"),
        ("heart_rate_daily", "Heart Rate (Daily)", "bpm", models.HeartRateDaily, "date"),
        ("sleep", "Sleep", "", models.SleepLog, "date"),
        ("spo2", "SpO2", "%", models.SpO2Daily, "date"),
        ("hrv", "Heart Rate Variability", "ms", models.HRVDaily, "date"),
        ("breathing_rate", "Breathing Rate", "breaths/min", models.BreathingRate, "date"),
        ("skin_temperature", "Skin Temperature", "°C", models.SkinTemperature, "date"),
        ("vo2_max", "VO2 Max", "mL/kg/min", models.VO2Max, "date"),
        ("activity", "Activity (Daily)", "", models.ActivityDaily, "date"),
        ("stress", "Stress Score", "", models.StressScore, "date"),
        ("readiness", "Readiness Score", "", models.ReadinessScore, "date"),
        ("exercises", "Exercises", "", models.Exercise, "date"),
    ]

    for name, label, unit, model, date_col in metric_configs:
        col = getattr(model, date_col)
        result = db.query(func.min(col), func.max(col), func.count()).first()
        if result and result[2] > 0:
            start = result[0]
            end = result[1]
            # Convert datetime to date string if needed
            if isinstance(start, datetime):
                start = start.date()
            if isinstance(end, datetime):
                end = end.date()
            metrics.append({
                "name": name,
                "label": label,
                "unit": unit,
                "startDate": str(start),
                "endDate": str(end),
                "count": result[2],
            })

    return {"metrics": metrics}


# ─── Overview ─────────────────────────────────────────────────

@router.get("/data/overview")
def get_overview(
    date_str: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    """Get a snapshot of all metrics for a single day."""
    target = date.fromisoformat(date_str) if date_str else date.today()

    hr_daily = db.query(models.HeartRateDaily).filter(
        models.HeartRateDaily.date == target
    ).first()

    sleep = db.query(models.SleepLog).filter(
        models.SleepLog.date == target
    ).first()

    activity = db.query(models.ActivityDaily).filter(
        models.ActivityDaily.date == target
    ).first()

    spo2 = db.query(models.SpO2Daily).filter(
        models.SpO2Daily.date == target
    ).first()

    hrv = db.query(models.HRVDaily).filter(
        models.HRVDaily.date == target
    ).first()

    br = db.query(models.BreathingRate).filter(
        models.BreathingRate.date == target
    ).first()

    temp = db.query(models.SkinTemperature).filter(
        models.SkinTemperature.date == target
    ).first()

    vo2 = db.query(models.VO2Max).filter(
        models.VO2Max.date == target
    ).first()

    stress = db.query(models.StressScore).filter(
        models.StressScore.date == target
    ).first()

    readiness = db.query(models.ReadinessScore).filter(
        models.ReadinessScore.date == target
    ).first()

    return {
        "date": str(target),
        "heartRate": _serialize(hr_daily, [
            "resting_heart_rate", "fat_burn_minutes", "cardio_minutes", "peak_minutes"
        ]),
        "sleep": _serialize(sleep, [
            "start_time", "end_time", "duration_ms", "efficiency",
            "minutes_asleep", "minutes_awake", "overall_score",
            "deep_sleep_minutes", "rem_sleep_minutes", "light_sleep_minutes"
        ]),
        "activity": _serialize(activity, [
            "steps", "distance_km", "calories_total", "calories_active",
            "minutes_sedentary", "minutes_lightly_active",
            "minutes_fairly_active", "minutes_very_active", "active_zone_minutes"
        ]),
        "spo2": _serialize(spo2, ["avg_spo2", "min_spo2", "max_spo2"]),
        "hrv": _serialize(hrv, ["daily_rmssd", "deep_rmssd"]),
        "breathingRate": _serialize(br, ["breathing_rate"]),
        "skinTemperature": _serialize(temp, ["relative_temp"]),
        "vo2Max": _serialize(vo2, ["vo2_max"]),
        "stress": _serialize(stress, [
            "stress_score", "exertion_score", "responsiveness_score"
        ]),
        "readiness": _serialize(readiness, ["readiness_score"]),
    }


def _serialize(obj, fields):
    if obj is None:
        return None
    result = {}
    for f in fields:
        val = getattr(obj, f, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        elif isinstance(val, date):
            val = str(val)
        result[f] = val
    return result


# ─── Heart Rate ───────────────────────────────────────────────

@router.get("/data/heart-rate/intraday")
def get_heart_rate_intraday(
    date_str: str = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    """Get per-second/per-5-second HR data for a single day."""
    target = date.fromisoformat(date_str)
    start_dt, end_dt = _dt_range(target, target)

    rows = db.query(models.HeartRateIntraday).filter(
        and_(
            models.HeartRateIntraday.timestamp >= start_dt,
            models.HeartRateIntraday.timestamp < end_dt,
        )
    ).order_by(models.HeartRateIntraday.timestamp).all()

    return {
        "date": date_str,
        "data": [
            {"timestamp": r.timestamp.isoformat(), "bpm": r.bpm, "confidence": r.confidence}
            for r in rows
        ],
    }


@router.get("/data/heart-rate/daily")
def get_heart_rate_daily(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get daily HR summaries (resting HR, zones) over a date range."""
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.HeartRateDaily).filter(
        and_(models.HeartRateDaily.date >= start_date, models.HeartRateDaily.date <= end_date)
    ).order_by(models.HeartRateDaily.date).all()

    return {
        "data": [
            {
                "date": str(r.date),
                "restingHeartRate": r.resting_heart_rate,
                "fatBurnMinutes": r.fat_burn_minutes,
                "cardioMinutes": r.cardio_minutes,
                "peakMinutes": r.peak_minutes,
            }
            for r in rows
        ]
    }


# ─── Sleep ────────────────────────────────────────────────────

@router.get("/data/sleep")
def get_sleep_logs(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.SleepLog).filter(
        and_(models.SleepLog.date >= start_date, models.SleepLog.date <= end_date)
    ).order_by(models.SleepLog.date).all()

    return {
        "data": [
            {
                "id": r.id, "date": str(r.date),
                "startTime": r.start_time.isoformat(), "endTime": r.end_time.isoformat(),
                "durationMs": r.duration_ms, "efficiency": r.efficiency,
                "minutesAsleep": r.minutes_asleep, "minutesAwake": r.minutes_awake,
                "overallScore": r.overall_score, "compositionScore": r.composition_score,
                "revitalizationScore": r.revitalization_score, "durationScore": r.duration_score,
                "deepSleepMinutes": r.deep_sleep_minutes, "remSleepMinutes": r.rem_sleep_minutes,
                "lightSleepMinutes": r.light_sleep_minutes,
            }
            for r in rows
        ]
    }


@router.get("/data/sleep/stages/{sleep_log_id}")
def get_sleep_stages(sleep_log_id: int, db: Session = Depends(get_db)):
    rows = db.query(models.SleepStage).filter(
        models.SleepStage.sleep_log_id == sleep_log_id
    ).order_by(models.SleepStage.timestamp).all()

    return {
        "data": [
            {
                "timestamp": r.timestamp.isoformat(),
                "stage": r.stage,
                "durationSeconds": r.duration_seconds,
            }
            for r in rows
        ]
    }


# ─── SpO2 ─────────────────────────────────────────────────────

@router.get("/data/spo2")
def get_spo2(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.SpO2Daily).filter(
        and_(models.SpO2Daily.date >= start_date, models.SpO2Daily.date <= end_date)
    ).order_by(models.SpO2Daily.date).all()

    return {
        "data": [
            {"date": str(r.date), "avg": r.avg_spo2, "min": r.min_spo2, "max": r.max_spo2}
            for r in rows
        ]
    }


@router.get("/data/spo2/intraday")
def get_spo2_intraday(
    date_str: str = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    target = date.fromisoformat(date_str)
    start_dt, end_dt = _dt_range(target, target)

    rows = db.query(models.SpO2Intraday).filter(
        and_(models.SpO2Intraday.timestamp >= start_dt, models.SpO2Intraday.timestamp < end_dt)
    ).order_by(models.SpO2Intraday.timestamp).all()

    return {
        "data": [{"timestamp": r.timestamp.isoformat(), "spo2": r.spo2} for r in rows]
    }


# ─── HRV ──────────────────────────────────────────────────────

@router.get("/data/hrv")
def get_hrv(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.HRVDaily).filter(
        and_(models.HRVDaily.date >= start_date, models.HRVDaily.date <= end_date)
    ).order_by(models.HRVDaily.date).all()

    return {
        "data": [
            {"date": str(r.date), "dailyRmssd": r.daily_rmssd, "deepRmssd": r.deep_rmssd}
            for r in rows
        ]
    }


@router.get("/data/hrv/intraday")
def get_hrv_intraday(
    date_str: str = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    target = date.fromisoformat(date_str)
    start_dt, end_dt = _dt_range(target, target)

    rows = db.query(models.HRVIntraday).filter(
        and_(models.HRVIntraday.timestamp >= start_dt, models.HRVIntraday.timestamp < end_dt)
    ).order_by(models.HRVIntraday.timestamp).all()

    return {
        "data": [
            {"timestamp": r.timestamp.isoformat(), "rmssd": r.rmssd, "hf": r.hf, "lf": r.lf}
            for r in rows
        ]
    }


# ─── Breathing Rate ───────────────────────────────────────────

@router.get("/data/breathing-rate")
def get_breathing_rate(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.BreathingRate).filter(
        and_(models.BreathingRate.date >= start_date, models.BreathingRate.date <= end_date)
    ).order_by(models.BreathingRate.date).all()

    return {
        "data": [{"date": str(r.date), "breathingRate": r.breathing_rate} for r in rows]
    }


# ─── Skin Temperature ────────────────────────────────────────

@router.get("/data/skin-temperature")
def get_skin_temperature(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.SkinTemperature).filter(
        and_(models.SkinTemperature.date >= start_date, models.SkinTemperature.date <= end_date)
    ).order_by(models.SkinTemperature.date).all()

    return {
        "data": [{"date": str(r.date), "relativeTemp": r.relative_temp} for r in rows]
    }


# ─── VO2 Max ──────────────────────────────────────────────────

@router.get("/data/vo2-max")
def get_vo2_max(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.VO2Max).filter(
        and_(models.VO2Max.date >= start_date, models.VO2Max.date <= end_date)
    ).order_by(models.VO2Max.date).all()

    return {
        "data": [{"date": str(r.date), "vo2Max": r.vo2_max} for r in rows]
    }


# ─── Activity ─────────────────────────────────────────────────

@router.get("/data/activity")
def get_activity_daily(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.ActivityDaily).filter(
        and_(models.ActivityDaily.date >= start_date, models.ActivityDaily.date <= end_date)
    ).order_by(models.ActivityDaily.date).all()

    return {
        "data": [
            {
                "date": str(r.date), "steps": r.steps, "distanceKm": r.distance_km,
                "caloriesTotal": r.calories_total, "caloriesActive": r.calories_active,
                "minutesSedentary": r.minutes_sedentary,
                "minutesLightlyActive": r.minutes_lightly_active,
                "minutesFairlyActive": r.minutes_fairly_active,
                "minutesVeryActive": r.minutes_very_active,
                "activeZoneMinutes": r.active_zone_minutes,
            }
            for r in rows
        ]
    }


@router.get("/data/activity/intraday")
def get_activity_intraday(
    date_str: str = Query(..., alias="date"),
    metric: str = Query("steps"),
    db: Session = Depends(get_db),
):
    target = date.fromisoformat(date_str)
    start_dt, end_dt = _dt_range(target, target)

    rows = db.query(models.ActivityIntraday).filter(
        and_(
            models.ActivityIntraday.timestamp >= start_dt,
            models.ActivityIntraday.timestamp < end_dt,
            models.ActivityIntraday.metric == metric,
        )
    ).order_by(models.ActivityIntraday.timestamp).all()

    return {
        "data": [
            {"timestamp": r.timestamp.isoformat(), "value": r.value}
            for r in rows
        ]
    }


# ─── Stress ───────────────────────────────────────────────────

@router.get("/data/stress")
def get_stress_scores(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.StressScore).filter(
        and_(models.StressScore.date >= start_date, models.StressScore.date <= end_date)
    ).order_by(models.StressScore.date).all()

    return {
        "data": [
            {
                "date": str(r.date), "stressScore": r.stress_score,
                "exertionScore": r.exertion_score,
                "responsivenessScore": r.responsiveness_score,
            }
            for r in rows
        ]
    }


# ─── Readiness ────────────────────────────────────────────────

@router.get("/data/readiness")
def get_readiness_scores(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.ReadinessScore).filter(
        and_(models.ReadinessScore.date >= start_date, models.ReadinessScore.date <= end_date)
    ).order_by(models.ReadinessScore.date).all()

    return {
        "data": [{"date": str(r.date), "readinessScore": r.readiness_score} for r in rows]
    }


# ─── Exercises ────────────────────────────────────────────────

@router.get("/data/exercises")
def get_exercises(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    start_date, end_date = _date_range(start, end)

    rows = db.query(models.Exercise).filter(
        and_(models.Exercise.date >= start_date, models.Exercise.date <= end_date)
    ).order_by(models.Exercise.date).all()

    return {
        "data": [
            {
                "id": r.id, "date": str(r.date),
                "startTime": r.start_time.isoformat(),
                "activityName": r.activity_name,
                "durationMs": r.duration_ms,
                "calories": r.calories,
                "averageHeartRate": r.average_heart_rate,
                "steps": r.steps, "distanceKm": r.distance_km,
            }
            for r in rows
        ]
    }


# ─── Glucose ───────────────────────────────────────────────────

@router.get("/data/glucose")
def get_glucose_readings(
    date_str: str = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    """Get glucose readings for a specific day."""
    target_date = date.fromisoformat(date_str)
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

    readings = db.query(models.GlucoseReading).filter(
        and_(
            models.GlucoseReading.timestamp >= start_dt,
            models.GlucoseReading.timestamp < end_dt
        )
    ).order_by(models.GlucoseReading.timestamp).all()

    return {
        "date": date_str,
        "readings": [
            {
                "timestamp": r.timestamp.isoformat(),
                "value": r.value,
                "source": r.source
            }
            for r in readings
        ]
    }


@router.get("/data/glucose/daily")
def get_glucose_daily(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get daily glucose summaries."""
    start_date, end_date = _date_range(start, end)
    start_dt, end_dt = _dt_range(start_date, end_date)

    # Query with date grouping
    results = db.query(
        func.date(models.GlucoseReading.timestamp).label("date"),
        func.avg(models.GlucoseReading.value).label("avg"),
        func.min(models.GlucoseReading.value).label("min"),
        func.max(models.GlucoseReading.value).label("max"),
        func.count(models.GlucoseReading.id).label("count")
    ).filter(
        and_(
            models.GlucoseReading.timestamp >= start_dt,
            models.GlucoseReading.timestamp < end_dt
        )
    ).group_by(
        func.date(models.GlucoseReading.timestamp)
    ).order_by(
        func.date(models.GlucoseReading.timestamp)
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


@router.get("/data/glucose/time-in-range")
def get_glucose_time_in_range(
    start: Optional[str] = None,
    end: Optional[str] = None,
    low_threshold: int = Query(70),
    high_threshold: int = Query(180),
    db: Session = Depends(get_db),
):
    """Calculate time in range statistics."""
    start_date, end_date = _date_range(start, end)
    start_dt, end_dt = _dt_range(start_date, end_date)

    readings = db.query(models.GlucoseReading.value).filter(
        and_(
            models.GlucoseReading.timestamp >= start_dt,
            models.GlucoseReading.timestamp < end_dt
        )
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


@router.get("/data/glucose/agp")
def get_glucose_agp(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Calculate Ambulatory Glucose Profile (percentiles by hour of day)."""
    import numpy as np

    start_date, end_date = _date_range(start, end)
    # Default to 14 days for AGP
    if start is None:
        start_date = end_date - timedelta(days=14)

    start_dt, end_dt = _dt_range(start_date, end_date)

    readings = db.query(
        models.GlucoseReading.timestamp,
        models.GlucoseReading.value
    ).filter(
        and_(
            models.GlucoseReading.timestamp >= start_dt,
            models.GlucoseReading.timestamp < end_dt
        )
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


# ─── Correlations ─────────────────────────────────────────────

CORRELATION_METRICS = {
    "resting_hr": (models.HeartRateDaily, "date", "resting_heart_rate"),
    "hrv": (models.HRVDaily, "date", "daily_rmssd"),
    "spo2": (models.SpO2Daily, "date", "avg_spo2"),
    "breathing_rate": (models.BreathingRate, "date", "breathing_rate"),
    "skin_temp": (models.SkinTemperature, "date", "relative_temp"),
    "vo2_max": (models.VO2Max, "date", "vo2_max"),
    "sleep_score": (models.SleepLog, "date", "overall_score"),
    "sleep_efficiency": (models.SleepLog, "date", "efficiency"),
    "sleep_duration": (models.SleepLog, "date", "minutes_asleep"),
    "deep_sleep": (models.SleepLog, "date", "deep_sleep_minutes"),
    "rem_sleep": (models.SleepLog, "date", "rem_sleep_minutes"),
    "steps": (models.ActivityDaily, "date", "steps"),
    "calories": (models.ActivityDaily, "date", "calories_total"),
    "active_minutes": (models.ActivityDaily, "date", "minutes_very_active"),
    "active_zone_minutes": (models.ActivityDaily, "date", "active_zone_minutes"),
    "stress": (models.StressScore, "date", "stress_score"),
    "avg_glucose": None,  # Special handling - requires daily aggregation
}


def _get_glucose_daily_avg(db: Session, start_date: date, end_date: date) -> dict:
    """Get daily average glucose values as a date->value map."""
    start_dt, end_dt = _dt_range(start_date, end_date)

    results = db.query(
        func.date(models.GlucoseReading.timestamp).label("date"),
        func.avg(models.GlucoseReading.value).label("avg")
    ).filter(
        and_(
            models.GlucoseReading.timestamp >= start_dt,
            models.GlucoseReading.timestamp < end_dt
        )
    ).group_by(func.date(models.GlucoseReading.timestamp)).all()

    return {str(g.date): round(g.avg) for g in results}


def _get_metric_data(metric: str, db: Session, start_date: date, end_date: date) -> dict:
    """Fetch metric data and return as date->value map."""
    if metric == "avg_glucose":
        return _get_glucose_daily_avg(db, start_date, end_date)

    model, date_col, val_col = CORRELATION_METRICS[metric]
    rows = db.query(
        getattr(model, date_col), getattr(model, val_col)
    ).filter(
        and_(getattr(model, date_col) >= start_date, getattr(model, date_col) <= end_date)
    ).all()

    return {str(row[0]): row[1] for row in rows if row[1] is not None}


@router.get("/data/correlations")
def get_correlations(
    x: str = Query(...),
    y: str = Query(...),
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get paired data points for two metrics, matched by date, for scatter plots."""
    if x not in CORRELATION_METRICS or y not in CORRELATION_METRICS:
        available = list(CORRELATION_METRICS.keys())
        return {"error": f"Unknown metric. Available: {available}"}

    start_date, end_date = _date_range(start, end)
    # Extend default range for correlations
    if not start:
        start_date = end_date - timedelta(days=90)

    # Fetch both series (with special handling for glucose)
    x_map = _get_metric_data(x, db, start_date, end_date)
    y_map = _get_metric_data(y, db, start_date, end_date)

    common_dates = sorted(set(x_map.keys()) & set(y_map.keys()))
    points = [
        {"date": d, "x": x_map[d], "y": y_map[d]}
        for d in common_dates
    ]

    # Compute correlation coefficient
    r_value = None
    if len(points) >= 3:
        x_vals = [p["x"] for p in points]
        y_vals = [p["y"] for p in points]
        try:
            from scipy import stats
            r_value, p_value = stats.pearsonr(x_vals, y_vals)
            r_value = round(r_value, 4)
        except Exception:
            pass

    return {
        "xMetric": x,
        "yMetric": y,
        "correlation": r_value,
        "points": points,
        "availableMetrics": list(CORRELATION_METRICS.keys()),
    }


# ─── Resting HR Calculation ────────────────────────────────────

@router.post("/data/calculate-resting-hr")
def calculate_resting_hr(db: Session = Depends(get_db)):
    """
    Calculate daily resting heart rate from intraday data.

    Uses the standard method of finding the lowest 30-sample rolling average
    of heart rate readings. This typically occurs during deep sleep or rest.

    Processes all dates that have HeartRateIntraday data but no HeartRateDaily
    record (or missing resting_heart_rate).

    Returns:
        Dictionary with count of days processed.
    """
    from app.parsers.export_parser import calculate_resting_hr_from_intraday

    try:
        count = calculate_resting_hr_from_intraday(db)
        return {
            "success": True,
            "days_processed": count,
            "message": f"Calculated resting heart rate for {count} days"
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }


# ─── CGM Sync ──────────────────────────────────────────────────

from pydantic import BaseModel


class CGMSyncRequest(BaseModel):
    """Request body for CGM sync endpoint."""
    email: str
    password: str
    region: str = "us"  # "us" or "eu"


@router.post("/sync/cgm")
async def sync_cgm(
    request: CGMSyncRequest,
    db: Session = Depends(get_db)
):
    """
    Sync glucose data from LibreLinkUp.

    Authenticates with LibreLinkUp using provided credentials, fetches glucose
    readings from all connected patients, and imports them into the database.

    Args:
        request: CGMSyncRequest with email, password, and optional region

    Returns:
        Dictionary with sync results including readings imported count
    """
    from app.services.librelinkup import LibreLinkUpClient, LibreLinkUpError

    try:
        client = LibreLinkUpClient(
            email=request.email,
            password=request.password,
            region=request.region
        )

        # Authenticate
        if not await client.login():
            return {
                "success": False,
                "error": "Failed to authenticate with LibreLinkUp. Check email and password."
            }

        # Get connected patients
        connections = await client.get_connections()
        if not connections:
            return {
                "success": False,
                "error": "No connected patients found in LibreLinkUp account."
            }

        # Fetch and import readings from all connections
        total_imported = 0
        total_readings = 0

        for connection in connections:
            patient_id = connection.get("patientId")
            if not patient_id:
                continue

            readings = await client.get_readings(patient_id)
            total_readings += len(readings)

            # Import readings (avoid duplicates by timestamp)
            for r in readings:
                existing = db.query(models.GlucoseReading).filter(
                    models.GlucoseReading.timestamp == r["timestamp"]
                ).first()

                if not existing:
                    db.add(models.GlucoseReading(**r))
                    total_imported += 1

        db.commit()

        return {
            "success": True,
            "readings_imported": total_imported,
            "total_readings_fetched": total_readings,
            "connections_synced": len(connections),
            "source": "librelinkup"
        }

    except LibreLinkUpError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
