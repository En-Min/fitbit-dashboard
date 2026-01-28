# Fitbit Raw Data Dashboard — Design Document

## Overview

A full-stack dashboard to visualize **all** raw data collected by a Fitbit Inspire 3, including data the Fitbit app hides or only partially surfaces. Supports both historical data (via bulk export) and live sync (via Fitbit Web API).

## Architecture

```
┌─────────────────────────────────────────────────┐
│                React Frontend                    │
│  (Interactive charts, filters, date ranges,      │
│   correlation views)                             │
└──────────────────────┬──────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────┐
│              Python Backend (FastAPI)             │
│  - Serves processed data to frontend             │
│  - Handles Fitbit OAuth2 flow                    │
│  - Syncs new data from Fitbit API                │
│  - Parses bulk export ZIP files                  │
└──────────┬───────────────────┬──────────────────┘
           │                   │
    ┌──────┴──────┐    ┌──────┴──────┐
    │  SQLite DB  │    │  Fitbit API │
    │ (all data)  │    │  (live sync) │
    └─────────────┘    └─────────────┘
```

## Data Model

All data types collected by Fitbit Inspire 3:

| Category | Data | Granularity |
|---|---|---|
| Heart Rate | Continuous HR, resting HR, HR zones | Per-second (exercise), per-5-sec otherwise |
| HRV | RMSSD values during sleep | Nightly + intraday |
| SpO2 | Blood oxygen during sleep | Nightly + intraday |
| Skin Temperature | Variation from baseline (sleep) | Nightly |
| Breathing Rate | Avg breaths/min during sleep | Nightly + intraday |
| VO2 Max | Estimated cardio fitness score | Daily |
| Steps & Activity | Steps, distance, calories, AZM, intensity | Per-minute intraday |
| Sleep | Stages (wake/light/deep/REM), score, consistency | Per-30-sec intervals |
| Stress | Stress management score | Daily |
| Daily Readiness | Readiness score (Premium) | Daily |
| Exercises | Workouts with HR, duration, calories | Per-exercise |

## Dashboard Views

### 1. Overview Page
- Today's snapshot of all key metrics
- 7-day sparkline trends
- Anomaly highlights vs personal baseline

### 2. Heart Rate Deep Dive
- Full intraday HR timeline
- Resting HR trend over weeks/months
- HR zones distribution
- HRV trend and nightly detail

### 3. Sleep Analysis
- Sleep stage hypnogram (30-sec resolution)
- Sleep score breakdown
- SpO2 overlaid on sleep stages
- Breathing rate during sleep
- Skin temperature variation trend
- Sleep consistency patterns

### 4. Activity & Fitness
- Per-minute step/calorie heatmaps (time-of-day vs day-of-week)
- VO2 Max trend
- Active zone minutes breakdown
- Exercise log with HR overlay

### 5. Correlations & Custom Analysis
- Pick any two metrics, scatter-plot or overlay
- Derived/hidden parameter exploration

## Data Pipeline

### Bulk Export
- Upload ZIP from fitbit.com/settings/data/export
- Backend parses JSON files into SQLite

### Live Sync (Fitbit API)
- Personal app registered at dev.fitbit.com
- OAuth2 flow in dashboard UI
- On-demand or scheduled sync

## API Endpoints

- `POST /api/upload` — bulk export ZIP
- `POST /api/auth/fitbit` — OAuth2 callback
- `POST /api/sync` — trigger API sync
- `GET /api/data/{metric}` — query params: start, end, resolution
- `GET /api/correlations` — query params: x, y, start, end

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Recharts |
| Backend | Python + FastAPI |
| Database | SQLite |
| Auth | Fitbit OAuth2 (Personal app type) |
