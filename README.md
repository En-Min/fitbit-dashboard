# Fitbit Raw Data Dashboard

A full-stack health data visualization dashboard for Fitbit devices. View all your raw Fitbit data that the official app doesn't show — per-second heart rate, detailed sleep stages, HRV analysis, and custom metric correlations.

![Dashboard Preview](https://img.shields.io/badge/status-active-success) ![Python](https://img.shields.io/badge/python-3.11+-blue) ![React](https://img.shields.io/badge/react-19-61dafb) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

### Data Sources
- **Bulk Import**: Upload your Fitbit Google Takeout export (ZIP)
- **Live Sync**: Connect via OAuth2 and sync directly from Fitbit's API

### Dashboard Pages

| Page | Description |
|------|-------------|
| **Overview** | Daily health snapshot with 11 metric cards and status coloring |
| **Heart Rate** | Intraday timeline, resting HR trend, zone analysis, HRV tracking |
| **Sleep** | Sleep score trend, 30-second hypnogram, stage breakdown, vitals panel |
| **Activity** | Steps trend, hourly heatmap, activity minutes, VO2 Max, exercise log |
| **Correlations** | Scatter plots with trend lines, compare any two metrics |
| **Settings** | Upload exports, OAuth connect, manual sync trigger |

### Supported Data Types
- Heart Rate (per-second intraday + daily resting)
- Heart Rate Variability (RMSSD, HF/LF)
- Sleep (stages, scores, efficiency)
- SpO2 (daily + intraday)
- Activity (steps, calories, distance, floors)
- Breathing Rate
- Skin Temperature
- VO2 Max
- Stress Score
- Daily Readiness
- Exercises

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy, SQLite |
| **Frontend** | React 19, TypeScript, Vite, Recharts |
| **Auth** | OAuth2 Authorization Code Grant |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Fitbit Developer account (for live sync)

### 1. Clone the repo
```bash
git clone https://github.com/En-Min/fitbit-dashboard.git
cd fitbit-dashboard
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd frontend
npm install
```

### 4. Configure Fitbit OAuth (optional, for live sync)

1. Register an app at https://dev.fitbit.com/apps
2. Set **OAuth 2.0 Application Type** to **Personal** (required for intraday data)
3. Set **Redirect URL** to `http://localhost:8000/api/auth/callback`
4. Export your credentials:

```bash
export FITBIT_CLIENT_ID=your_client_id
export FITBIT_CLIENT_SECRET=your_client_secret
```

### 5. Run the servers

**Backend** (terminal 1):
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Frontend** (terminal 2):
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Usage

### Option A: Upload Fitbit Export
1. Go to https://www.fitbit.com/settings/data/export
2. Request and download your data export (ZIP)
3. In the dashboard, go to **Settings** → **Import Fitbit Export**
4. Upload the ZIP file

### Option B: Live Sync via OAuth
1. In **Settings**, click **Connect Fitbit**
2. Authorize the app on Fitbit's website
3. Click **Sync Now** to pull your data

> **Note**: Fitbit's API has rate limits (~150 requests/hour). For large historical imports, use the export method.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── models.py         # SQLAlchemy models (17 tables)
│   │   ├── database.py       # DB connection
│   │   ├── config.py         # Settings
│   │   ├── routers/
│   │   │   ├── data.py       # Data endpoints + correlations
│   │   │   ├── auth.py       # OAuth2 flow
│   │   │   └── upload.py     # ZIP upload
│   │   ├── parsers/
│   │   │   └── export_parser.py  # Google Takeout parser
│   │   └── services/
│   │       └── fitbit_sync.py    # API sync service
│   └── tests/                # 136 tests
├── frontend/
│   ├── src/
│   │   ├── pages/            # 6 dashboard pages
│   │   ├── components/       # Reusable components
│   │   ├── api/client.ts     # API client
│   │   └── types/index.ts    # TypeScript interfaces
│   └── tests/                # 19 tests
└── docs/plans/               # Design documents
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/metrics` | List available metrics with date ranges |
| GET | `/api/data/overview` | Daily summary for a date |
| GET | `/api/data/heart-rate/intraday` | Per-second HR for a day |
| GET | `/api/data/heart-rate/daily` | Daily HR summaries |
| GET | `/api/data/sleep` | Sleep logs |
| GET | `/api/data/sleep/stages/{id}` | 30-second sleep stages |
| GET | `/api/data/spo2` | SpO2 readings |
| GET | `/api/data/hrv` | HRV data |
| GET | `/api/data/activity` | Daily activity |
| GET | `/api/data/correlations` | Correlation analysis |
| POST | `/api/upload` | Upload export ZIP |
| GET | `/api/auth/fitbit` | Start OAuth flow |
| GET | `/api/auth/status` | Check auth status |
| POST | `/api/sync` | Trigger data sync |

## Running Tests

**Backend:**
```bash
cd backend
source venv/bin/activate
pytest -v
```

**Frontend:**
```bash
cd frontend
npm test
```

## License

MIT

## Acknowledgments

- Built with [Claude Code](https://claude.ai/code)
- Fitbit is a trademark of Fitbit LLC
