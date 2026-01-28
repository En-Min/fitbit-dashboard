# Fitbit Raw Data Dashboard — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full-stack dashboard (React + FastAPI + SQLite) to visualize all raw Fitbit Inspire 3 data with historical bulk import and live API sync.

**Architecture:** Python FastAPI backend with SQLite storage, React TypeScript frontend with Recharts. Data ingestion from both Google Takeout export ZIPs and Fitbit Web API via OAuth2.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite, React 18, TypeScript, Recharts, Vite

---

## Task 1: Backend Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`

Set up FastAPI app with CORS, SQLite connection via SQLAlchemy, and config for Fitbit credentials.

## Task 2: Database Models

**Files:**
- Create: `backend/app/models.py`

Tables: heart_rate, heart_rate_daily, sleep_log, sleep_stages, spo2, hrv, breathing_rate, skin_temperature, vo2_max, activity_daily, activity_intraday, stress_score, readiness_score, exercises, sync_status

## Task 3: Bulk Export Parser

**Files:**
- Create: `backend/app/parsers/__init__.py`
- Create: `backend/app/parsers/export_parser.py`

Parse Google Takeout ZIP structure:
- `Global Export Data/heart_rate-*.json`
- `Global Export Data/sleep-*.json`
- `Global Export Data/steps-*.json`
- `Global Export Data/calories-*.json`
- `Global Export Data/distance-*.json`
- `Global Export Data/altitude-*.json`
- `Sleep Score/*.csv`
- `Heart Rate Variability/*.csv`
- `Oxygen Saturation (SpO2)/*.csv`
- `Temperature/*.csv`
- `Stress Score/*.csv`
- `Daily Readiness/*.csv`
- `Active Zone Minutes (AZM)/*.csv`

## Task 4: FastAPI Endpoints — Data Upload & Query

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/upload.py`
- Create: `backend/app/routers/data.py`

Endpoints:
- `POST /api/upload` — accept ZIP, parse, store
- `GET /api/data/{metric}?start=&end=&resolution=` — generic query
- `GET /api/data/overview?date=` — today's snapshot
- `GET /api/data/correlations?x=&y=&start=&end=`
- `GET /api/metrics` — list available metrics and date ranges

## Task 5: Fitbit OAuth2 & API Sync

**Files:**
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/fitbit_sync.py`

OAuth2 Authorization Code flow, token storage, refresh. Sync endpoints for each data type using Fitbit Web API intraday endpoints.

## Task 6: Frontend Scaffolding

**Files:**
- Create: `frontend/` via Vite + React + TypeScript
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/components/Layout.tsx`

## Task 7: Overview Page

**Files:**
- Create: `frontend/src/pages/Overview.tsx`
- Create: `frontend/src/components/MetricCard.tsx`
- Create: `frontend/src/components/SparklineChart.tsx`

## Task 8: Heart Rate Deep Dive Page

**Files:**
- Create: `frontend/src/pages/HeartRate.tsx`
- Create: `frontend/src/components/IntradayTimeline.tsx`
- Create: `frontend/src/components/HRZonesChart.tsx`

## Task 9: Sleep Analysis Page

**Files:**
- Create: `frontend/src/pages/Sleep.tsx`
- Create: `frontend/src/components/Hypnogram.tsx`
- Create: `frontend/src/components/SleepMetrics.tsx`

## Task 10: Activity & Fitness Page

**Files:**
- Create: `frontend/src/pages/Activity.tsx`
- Create: `frontend/src/components/ActivityHeatmap.tsx`
- Create: `frontend/src/components/VO2MaxTrend.tsx`

## Task 11: Correlations Page

**Files:**
- Create: `frontend/src/pages/Correlations.tsx`
- Create: `frontend/src/components/ScatterPlot.tsx`
- Create: `frontend/src/components/MetricSelector.tsx`

## Task 12: Backend Tests

**Files:**
- Create: `backend/tests/test_models.py`
- Create: `backend/tests/test_parsers.py`
- Create: `backend/tests/test_api.py`
- Create: `backend/tests/test_auth.py`
- Create: `backend/tests/conftest.py`

## Task 13: Frontend Tests

**Files:**
- Create: `frontend/src/__tests__/`

## Task 14: Git — Final Commit

Stage all, commit with summary message.
