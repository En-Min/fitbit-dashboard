"""
Fitbit Web API sync service.

Performs incremental syncing for every supported data type.  Each data type
records its last-synced date in the ``SyncStatus`` table so only new data is
fetched on subsequent runs.

Public entry points
-------------------
- ``sync_all(db)`` -- async, syncs every data type from last_synced to today.
- ``run_sync_background()`` -- sync-safe wrapper intended for FastAPI
  ``BackgroundTasks``; creates its own DB session.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from app.config import settings
from app.database import SessionLocal
from app.models import (
    ActivityDaily,
    ActivityIntraday,
    BreathingRate,
    Exercise,
    HeartRateDaily,
    HeartRateIntraday,
    HRVDaily,
    HRVIntraday,
    OAuthToken,
    SkinTemperature,
    SleepLog,
    SleepStage,
    SpO2Daily,
    SpO2Intraday,
    SyncStatus,
    VO2Max,
)

logger = logging.getLogger("fitbit_sync")

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _get_stored_token(db: Session) -> OAuthToken | None:
    return db.query(OAuthToken).order_by(OAuthToken.id.desc()).first()


async def _ensure_valid_token(db: Session) -> str:
    """Return a valid Bearer access_token, refreshing if necessary."""
    token = _get_stored_token(db)
    if token is None:
        raise RuntimeError("No OAuth token in database -- user must authenticate first.")

    if time.time() >= (token.expires_at - 60):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.FITBIT_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token,
                    "client_id": settings.FITBIT_CLIENT_ID,
                },
                auth=(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Token refresh failed ({resp.status_code}): {resp.text}")
            data = resp.json()
            token.access_token = data["access_token"]
            token.refresh_token = data["refresh_token"]
            token.expires_at = time.time() + data.get("expires_in", 28800)
            token.token_type = data.get("token_type", "Bearer")
            token.scope = data.get("scope", "")
            token.user_id = data.get("user_id", token.user_id)
            db.commit()
            db.refresh(token)

    return token.access_token


# ---------------------------------------------------------------------------
# Generic API request helper
# ---------------------------------------------------------------------------

async def _api_get(
    client: httpx.AsyncClient,
    path: str,
    db: Session,
) -> dict[str, Any] | None:
    """Make an authenticated GET to the Fitbit Web API.

    Transparently retries once on a 401 by refreshing the token.
    Returns parsed JSON or ``None`` if the endpoint returned no useful data.
    """
    access_token = await _ensure_valid_token(db)

    resp = await client.get(
        f"{settings.FITBIT_API_BASE}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Handle token expiry mid-session
    if resp.status_code == 401:
        access_token = await _ensure_valid_token(db)
        resp = await client.get(
            f"{settings.FITBIT_API_BASE}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "60"))
        logger.warning("Rate-limited by Fitbit API. Retry-After: %s seconds", retry_after)
        return None

    if resp.status_code not in (200, 201):
        logger.warning("Fitbit API %s returned %s: %s", path, resp.status_code, resp.text[:300])
        return None

    return resp.json()


# ---------------------------------------------------------------------------
# SyncStatus helpers
# ---------------------------------------------------------------------------

def _get_last_synced(db: Session, data_type: str) -> date:
    """Return the last-synced date for *data_type*, or 30 days ago."""
    row = db.query(SyncStatus).filter(SyncStatus.data_type == data_type).first()
    if row is None:
        return date.today() - timedelta(days=30)
    return row.last_synced.date() if isinstance(row.last_synced, datetime) else row.last_synced


def _set_last_synced(db: Session, data_type: str, synced_date: date) -> None:
    row = db.query(SyncStatus).filter(SyncStatus.data_type == data_type).first()
    ts = datetime.combine(synced_date, datetime.min.time())
    if row is None:
        db.add(SyncStatus(data_type=data_type, last_synced=ts))
    else:
        row.last_synced = ts
    db.commit()


def _date_range(start: date, end: date):
    """Yield dates from *start* to *end* inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


# ---------------------------------------------------------------------------
# Individual sync functions
# ---------------------------------------------------------------------------

async def sync_heart_rate_intraday(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch 1-second heart rate intraday data for *day*."""
    ds = day.isoformat()
    data = await _api_get(client, f"/1/user/-/activities/heart/date/{ds}/1d/1sec.json", db)
    if data is None:
        return

    dataset = (
        data.get("activities-heart-intraday", {})
        .get("dataset", [])
    )
    if not dataset:
        return

    rows: list[dict] = []
    for entry in dataset:
        ts = datetime.combine(day, datetime.strptime(entry["time"], "%H:%M:%S").time())
        rows.append({"timestamp": ts, "bpm": entry["value"], "confidence": None})

    # Bulk upsert: skip conflicts on the unique timestamp index
    stmt = sqlite_upsert(HeartRateIntraday.__table__).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["timestamp"])
    db.execute(stmt)
    db.commit()


async def sync_heart_rate_daily(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch daily heart rate summary for *day*."""
    ds = day.isoformat()
    data = await _api_get(client, f"/1/user/-/activities/heart/date/{ds}/1d.json", db)
    if data is None:
        return

    heart_list = data.get("activities-heart", [])
    if not heart_list:
        return

    entry = heart_list[0]
    value = entry.get("value", {})

    resting_hr = value.get("restingHeartRate")
    zones = {z["name"]: z.get("minutes", 0) for z in value.get("heartRateZones", [])}

    stmt = sqlite_upsert(HeartRateDaily.__table__).values(
        date=day,
        resting_heart_rate=resting_hr,
        fat_burn_minutes=zones.get("Fat Burn"),
        cardio_minutes=zones.get("Cardio"),
        peak_minutes=zones.get("Peak"),
        out_of_range_minutes=zones.get("Out of Range"),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["date"],
        set_={
            "resting_heart_rate": stmt.excluded.resting_heart_rate,
            "fat_burn_minutes": stmt.excluded.fat_burn_minutes,
            "cardio_minutes": stmt.excluded.cardio_minutes,
            "peak_minutes": stmt.excluded.peak_minutes,
            "out_of_range_minutes": stmt.excluded.out_of_range_minutes,
        },
    )
    db.execute(stmt)
    db.commit()


async def sync_sleep(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch sleep data for *day*."""
    ds = day.isoformat()
    data = await _api_get(client, f"/1.2/user/-/sleep/date/{ds}.json", db)
    if data is None:
        return

    for s in data.get("sleep", []):
        log_id = str(s.get("logId", ""))
        start_time = datetime.fromisoformat(s["startTime"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(s["endTime"].replace("Z", "+00:00"))

        # Sleep stages summary
        stages_summary = s.get("levels", {}).get("summary", {})
        deep = stages_summary.get("deep", {}).get("minutes")
        rem = stages_summary.get("rem", {}).get("minutes")
        light = stages_summary.get("light", {}).get("minutes")

        stmt = sqlite_upsert(SleepLog.__table__).values(
            log_id=log_id,
            date=day,
            start_time=start_time,
            end_time=end_time,
            duration_ms=s.get("duration"),
            efficiency=s.get("efficiency"),
            minutes_asleep=s.get("minutesAsleep"),
            minutes_awake=s.get("minutesAwake"),
            time_in_bed=s.get("timeInBed"),
            type=s.get("type"),
            overall_score=None,
            composition_score=None,
            revitalization_score=None,
            duration_score=None,
            deep_sleep_minutes=deep,
            rem_sleep_minutes=rem,
            light_sleep_minutes=light,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["log_id"],
            set_={
                "start_time": stmt.excluded.start_time,
                "end_time": stmt.excluded.end_time,
                "duration_ms": stmt.excluded.duration_ms,
                "efficiency": stmt.excluded.efficiency,
                "minutes_asleep": stmt.excluded.minutes_asleep,
                "minutes_awake": stmt.excluded.minutes_awake,
                "time_in_bed": stmt.excluded.time_in_bed,
                "type": stmt.excluded.type,
                "deep_sleep_minutes": stmt.excluded.deep_sleep_minutes,
                "rem_sleep_minutes": stmt.excluded.rem_sleep_minutes,
                "light_sleep_minutes": stmt.excluded.light_sleep_minutes,
            },
        )
        db.execute(stmt)
        db.commit()

        # Fetch the row back to get the database PK for sleep stages
        sleep_row = db.query(SleepLog).filter(SleepLog.log_id == log_id).first()
        if sleep_row is None:
            continue

        # Sleep stages detail
        levels_data = s.get("levels", {}).get("data", [])
        if levels_data:
            stage_rows: list[dict] = []
            for lev in levels_data:
                ts = datetime.fromisoformat(lev["dateTime"].replace("Z", "+00:00"))
                stage_rows.append({
                    "sleep_log_id": sleep_row.id,
                    "timestamp": ts,
                    "stage": lev["level"],
                    "duration_seconds": lev.get("seconds"),
                })
            if stage_rows:
                stmt_stages = sqlite_upsert(SleepStage.__table__).values(stage_rows)
                stmt_stages = stmt_stages.on_conflict_do_nothing()
                db.execute(stmt_stages)
                db.commit()


async def sync_spo2(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch daily SpO2 summary and intraday readings for *day*."""
    ds = day.isoformat()

    # Daily summary
    data = await _api_get(client, f"/1/user/-/spo2/date/{ds}.json", db)
    if data and "value" in data:
        val = data["value"]
        stmt = sqlite_upsert(SpO2Daily.__table__).values(
            date=day,
            avg_spo2=val.get("avg"),
            min_spo2=val.get("min"),
            max_spo2=val.get("max"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={
                "avg_spo2": stmt.excluded.avg_spo2,
                "min_spo2": stmt.excluded.min_spo2,
                "max_spo2": stmt.excluded.max_spo2,
            },
        )
        db.execute(stmt)
        db.commit()

    # Intraday
    intra = await _api_get(client, f"/1/user/-/spo2/date/{ds}/all.json", db)
    if intra and "minutes" in intra:
        rows: list[dict] = []
        for m in intra["minutes"]:
            ts = datetime.fromisoformat(m["minute"].replace("Z", "+00:00"))
            rows.append({"timestamp": ts, "spo2": m["value"]})
        if rows:
            stmt_i = sqlite_upsert(SpO2Intraday.__table__).values(rows)
            stmt_i = stmt_i.on_conflict_do_nothing(index_elements=["timestamp"])
            db.execute(stmt_i)
            db.commit()


async def sync_hrv(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch daily HRV summary and intraday for *day*."""
    ds = day.isoformat()

    # Daily
    data = await _api_get(client, f"/1/user/-/hrv/date/{ds}.json", db)
    if data and data.get("hrv"):
        for hrv_entry in data["hrv"]:
            val = hrv_entry.get("value", {})
            stmt = sqlite_upsert(HRVDaily.__table__).values(
                date=day,
                daily_rmssd=val.get("dailyRmssd"),
                deep_rmssd=val.get("deepRmssd"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["date"],
                set_={
                    "daily_rmssd": stmt.excluded.daily_rmssd,
                    "deep_rmssd": stmt.excluded.deep_rmssd,
                },
            )
            db.execute(stmt)
            db.commit()

    # Intraday
    intra = await _api_get(client, f"/1/user/-/hrv/date/{ds}/all.json", db)
    if intra and intra.get("hrv"):
        rows: list[dict] = []
        for hrv_entry in intra["hrv"]:
            for m in hrv_entry.get("minutes", []):
                ts = datetime.fromisoformat(m["minute"].replace("Z", "+00:00"))
                val = m.get("value", {})
                rows.append({
                    "timestamp": ts,
                    "rmssd": val.get("rmssd", 0),
                    "coverage": val.get("coverage"),
                    "hf": val.get("hf"),
                    "lf": val.get("lf"),
                })
        if rows:
            stmt_i = sqlite_upsert(HRVIntraday.__table__).values(rows)
            stmt_i = stmt_i.on_conflict_do_nothing(index_elements=["timestamp"])
            db.execute(stmt_i)
            db.commit()


async def sync_breathing_rate(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch breathing rate for *day*."""
    ds = day.isoformat()
    data = await _api_get(client, f"/1/user/-/br/date/{ds}.json", db)
    if data is None:
        return

    for entry in data.get("br", []):
        val = entry.get("value", {})
        br_value = val.get("breathingRate")
        if br_value is None:
            continue
        stmt = sqlite_upsert(BreathingRate.__table__).values(
            date=day,
            breathing_rate=br_value,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={"breathing_rate": stmt.excluded.breathing_rate},
        )
        db.execute(stmt)
        db.commit()


async def sync_skin_temperature(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch skin temperature for *day*."""
    ds = day.isoformat()
    data = await _api_get(client, f"/1/user/-/temp/skin/date/{ds}.json", db)
    if data is None:
        return

    for entry in data.get("tempSkin", []):
        val = entry.get("value", {})
        relative = val.get("nightlyRelative")
        if relative is None:
            continue
        stmt = sqlite_upsert(SkinTemperature.__table__).values(
            date=day,
            relative_temp=relative,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={"relative_temp": stmt.excluded.relative_temp},
        )
        db.execute(stmt)
        db.commit()


async def sync_vo2_max(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch VO2 Max (cardio fitness score) for *day*."""
    ds = day.isoformat()
    data = await _api_get(client, f"/1/user/-/cardioscore/date/{ds}.json", db)
    if data is None:
        return

    for entry in data.get("cardioScore", []):
        val = entry.get("value", {})
        vo2 = val.get("vo2Max")
        if vo2 is None:
            continue
        stmt = sqlite_upsert(VO2Max.__table__).values(
            date=day,
            vo2_max=vo2,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={"vo2_max": stmt.excluded.vo2_max},
        )
        db.execute(stmt)
        db.commit()


async def sync_activity_daily(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch daily activity summary for *day*."""
    ds = day.isoformat()
    data = await _api_get(client, f"/1/user/-/activities/date/{ds}.json", db)
    if data is None:
        return

    summary = data.get("summary", {})
    if not summary:
        return

    distances = {d["activity"]: d["distance"] for d in summary.get("distances", [])}

    stmt = sqlite_upsert(ActivityDaily.__table__).values(
        date=day,
        steps=summary.get("steps"),
        distance_km=distances.get("total"),
        floors=summary.get("floors"),
        calories_total=summary.get("caloriesOut"),
        calories_active=summary.get("activityCalories"),
        minutes_sedentary=summary.get("sedentaryMinutes"),
        minutes_lightly_active=summary.get("lightlyActiveMinutes"),
        minutes_fairly_active=summary.get("fairlyActiveMinutes"),
        minutes_very_active=summary.get("veryActiveMinutes"),
        active_zone_minutes=summary.get("activeZoneMinutes", {}).get("totalMinutes")
        if isinstance(summary.get("activeZoneMinutes"), dict) else None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["date"],
        set_={
            "steps": stmt.excluded.steps,
            "distance_km": stmt.excluded.distance_km,
            "floors": stmt.excluded.floors,
            "calories_total": stmt.excluded.calories_total,
            "calories_active": stmt.excluded.calories_active,
            "minutes_sedentary": stmt.excluded.minutes_sedentary,
            "minutes_lightly_active": stmt.excluded.minutes_lightly_active,
            "minutes_fairly_active": stmt.excluded.minutes_fairly_active,
            "minutes_very_active": stmt.excluded.minutes_very_active,
            "active_zone_minutes": stmt.excluded.active_zone_minutes,
        },
    )
    db.execute(stmt)
    db.commit()


async def sync_activity_intraday(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch per-minute intraday steps, calories, and distance for *day*."""
    ds = day.isoformat()
    resources = {
        "steps": "activities-steps-intraday",
        "calories": "activities-calories-intraday",
        "distance": "activities-distance-intraday",
    }

    for resource_name, response_key in resources.items():
        data = await _api_get(
            client,
            f"/1/user/-/activities/{resource_name}/date/{ds}/1d/1min.json",
            db,
        )
        if data is None:
            continue

        dataset = data.get(response_key, {}).get("dataset", [])
        if not dataset:
            continue

        rows: list[dict] = []
        for entry in dataset:
            ts = datetime.combine(day, datetime.strptime(entry["time"], "%H:%M:%S").time())
            rows.append({
                "timestamp": ts,
                "metric": resource_name,
                "value": float(entry["value"]),
            })

        if rows:
            stmt = sqlite_upsert(ActivityIntraday.__table__).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["timestamp", "metric"])
            db.execute(stmt)
            db.commit()


async def sync_exercises(
    client: httpx.AsyncClient, db: Session, day: date
) -> None:
    """Fetch exercise list.

    The ``/activities/list.json`` endpoint is paginated and date-filtered.
    We request activities after the *day* start.
    """
    after_ts = datetime.combine(day, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%S")
    before_ts = datetime.combine(day + timedelta(days=1), datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%S")
    data = await _api_get(
        client,
        f"/1/user/-/activities/list.json?afterDate={day.isoformat()}&sort=asc&limit=100&offset=0",
        db,
    )
    if data is None:
        return

    for a in data.get("activities", []):
        start_str = a.get("startTime", a.get("originalStartTime", ""))
        if not start_str:
            continue

        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        activity_date = start_time.date()

        # Only process exercises for the target day
        if activity_date != day:
            continue

        end_time = None
        duration_ms = a.get("activeDuration") or a.get("duration")
        if duration_ms and start_time:
            end_time = start_time + timedelta(milliseconds=duration_ms)

        log_id = str(a.get("logId", ""))

        stmt = sqlite_upsert(Exercise.__table__).values(
            log_id=log_id,
            date=activity_date,
            start_time=start_time,
            end_time=end_time,
            activity_name=a.get("activityName", "Unknown"),
            duration_ms=duration_ms,
            calories=a.get("calories"),
            average_heart_rate=a.get("averageHeartRate"),
            steps=a.get("steps"),
            distance_km=a.get("distance"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["log_id"],
            set_={
                "start_time": stmt.excluded.start_time,
                "end_time": stmt.excluded.end_time,
                "activity_name": stmt.excluded.activity_name,
                "duration_ms": stmt.excluded.duration_ms,
                "calories": stmt.excluded.calories,
                "average_heart_rate": stmt.excluded.average_heart_rate,
                "steps": stmt.excluded.steps,
                "distance_km": stmt.excluded.distance_km,
            },
        )
        db.execute(stmt)
        db.commit()


# ---------------------------------------------------------------------------
# Master sync orchestrator
# ---------------------------------------------------------------------------

# Map data-type key -> (sync function, SyncStatus key)
_SYNC_REGISTRY: list[tuple[str, Any]] = [
    ("heart_rate_daily", sync_heart_rate_daily),
    ("heart_rate_intraday", sync_heart_rate_intraday),
    ("sleep", sync_sleep),
    ("spo2", sync_spo2),
    ("hrv", sync_hrv),
    ("breathing_rate", sync_breathing_rate),
    ("skin_temperature", sync_skin_temperature),
    ("vo2_max", sync_vo2_max),
    ("activity_daily", sync_activity_daily),
    ("activity_intraday", sync_activity_intraday),
    ("exercises", sync_exercises),
]


async def sync_all(db: Session) -> dict[str, str]:
    """Run an incremental sync for every data type.

    Returns a mapping of data_type -> status string.
    """
    today = date.today()
    results: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        for data_type, sync_fn in _SYNC_REGISTRY:
            last = _get_last_synced(db, data_type)
            # Start one day after last sync to avoid re-fetching
            start = last + timedelta(days=1)
            if start > today:
                results[data_type] = "already_up_to_date"
                logger.info("%s: already up to date", data_type)
                continue

            logger.info("%s: syncing from %s to %s", data_type, start, today)
            synced_days = 0
            try:
                for day in _date_range(start, today):
                    await sync_fn(client, db, day)
                    synced_days += 1
                _set_last_synced(db, data_type, today)
                results[data_type] = f"synced_{synced_days}_days"
                logger.info("%s: synced %d days", data_type, synced_days)
            except Exception:
                logger.exception("Error syncing %s", data_type)
                # Record partial progress up to yesterday if we synced any days
                if synced_days > 0:
                    partial_date = start + timedelta(days=synced_days - 1)
                    _set_last_synced(db, data_type, partial_date)
                results[data_type] = f"error_after_{synced_days}_days"

    return results


def run_sync_background() -> None:
    """Synchronous wrapper for ``sync_all`` for use with FastAPI BackgroundTasks.

    Creates its own DB session and event loop.
    """
    import asyncio

    db = SessionLocal()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(sync_all(db))
            logger.info("Background sync complete: %s", results)
        finally:
            loop.close()
    except Exception:
        logger.exception("Background sync failed")
    finally:
        db.close()
