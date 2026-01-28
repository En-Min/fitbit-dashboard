import { useState, useEffect, useCallback } from "react";
import {
  LayoutDashboard,
  Heart,
  Moon,
  Footprints,
  Wind,
  Thermometer,
  Activity,
  Brain,
  Flame,
  Timer,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  TrendingUp,
  Droplets,
} from "lucide-react";

// ─── Types ──────────────────────────────────────────────────────

interface OverviewResponse {
  date: string;
  heartRate: {
    resting_heart_rate: number | null;
    fat_burn_minutes: number | null;
    cardio_minutes: number | null;
    peak_minutes: number | null;
  } | null;
  sleep: {
    start_time: string | null;
    end_time: string | null;
    duration_ms: number | null;
    efficiency: number | null;
    minutes_asleep: number | null;
    minutes_awake: number | null;
    overall_score: number | null;
    deep_sleep_minutes: number | null;
    rem_sleep_minutes: number | null;
    light_sleep_minutes: number | null;
  } | null;
  activity: {
    steps: number | null;
    distance_km: number | null;
    calories_total: number | null;
    calories_active: number | null;
    minutes_sedentary: number | null;
    minutes_lightly_active: number | null;
    minutes_fairly_active: number | null;
    minutes_very_active: number | null;
    active_zone_minutes: number | null;
  } | null;
  spo2: {
    avg_spo2: number | null;
    min_spo2: number | null;
    max_spo2: number | null;
  } | null;
  hrv: {
    daily_rmssd: number | null;
    deep_rmssd: number | null;
  } | null;
  breathingRate: {
    breathing_rate: number | null;
  } | null;
  skinTemperature: {
    relative_temp: number | null;
  } | null;
  vo2Max: {
    vo2_max: number | null;
  } | null;
  stress: {
    stress_score: number | null;
    exertion_score: number | null;
    responsiveness_score: number | null;
  } | null;
}

// ─── Health range status ────────────────────────────────────────

type HealthStatus = "green" | "yellow" | "red" | "neutral";

function getHealthStatus(
  metric: string,
  value: number | null | undefined
): HealthStatus {
  if (value == null) return "neutral";

  switch (metric) {
    case "restingHR":
      if (value >= 40 && value <= 70) return "green";
      if (value > 70 && value <= 85) return "yellow";
      return "red";

    case "sleepScore":
      if (value >= 80) return "green";
      if (value >= 60) return "yellow";
      return "red";

    case "steps":
      if (value >= 10000) return "green";
      if (value >= 5000) return "yellow";
      return "red";

    case "spo2":
      if (value >= 95) return "green";
      if (value >= 90) return "yellow";
      return "red";

    case "hrv":
      if (value >= 30) return "green";
      if (value >= 15) return "yellow";
      return "red";

    case "breathingRate":
      if (value >= 12 && value <= 20) return "green";
      if (value >= 10 && value <= 24) return "yellow";
      return "red";

    case "skinTemp":
      if (Math.abs(value) <= 1.0) return "green";
      if (Math.abs(value) <= 2.0) return "yellow";
      return "red";

    case "vo2max":
      if (value >= 40) return "green";
      if (value >= 30) return "yellow";
      return "red";

    case "stress":
      // Fitbit stress: higher = more resilient (better)
      if (value >= 70) return "green";
      if (value >= 40) return "yellow";
      return "red";

    case "activeZone":
      if (value >= 22) return "green";
      if (value >= 10) return "yellow";
      return "red";

    case "calories":
      // Calories are informational, no strong "bad" range
      if (value >= 1800) return "green";
      if (value >= 1200) return "yellow";
      return "red";

    default:
      return "neutral";
  }
}

const STATUS_COLORS: Record<HealthStatus, string> = {
  green: "var(--success)",
  yellow: "var(--warning)",
  red: "var(--error)",
  neutral: "var(--text-muted)",
};

const STATUS_BG: Record<HealthStatus, string> = {
  green: "var(--success-dim)",
  yellow: "rgba(251, 191, 36, 0.15)",
  red: "var(--error-dim)",
  neutral: "var(--bg-tertiary)",
};

// ─── MetricCard ─────────────────────────────────────────────────

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number | null | undefined;
  unit: string;
  statusKey: string;
  rawValue: number | null | undefined;
  subtitle?: string;
}

function MetricCard({
  icon,
  label,
  value,
  unit,
  statusKey,
  rawValue,
  subtitle,
}: MetricCardProps) {
  const status = getHealthStatus(statusKey, rawValue);
  const statusColor = STATUS_COLORS[status];
  const statusBg = STATUS_BG[status];
  const hasValue = value != null && value !== "--";

  return (
    <div
      style={{
        background: "var(--bg-secondary)",
        border: "1px solid var(--border-color)",
        borderRadius: "var(--radius)",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        position: "relative",
        overflow: "hidden",
        transition: "border-color 0.15s ease, transform 0.15s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = statusColor;
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--border-color)";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      {/* Status accent bar at top */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "3px",
          background: statusColor,
          opacity: hasValue ? 1 : 0.3,
        }}
      />

      {/* Header row: icon + label */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "8px",
            background: statusBg,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: statusColor,
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
        <span
          style={{
            fontSize: "13px",
            fontWeight: 500,
            color: "var(--text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
          }}
        >
          {label}
        </span>
      </div>

      {/* Value */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: "4px",
          }}
        >
          <span
            style={{
              fontSize: "28px",
              fontWeight: 700,
              color: hasValue ? "var(--text-primary)" : "var(--text-muted)",
              letterSpacing: "-0.02em",
              lineHeight: 1.1,
            }}
          >
            {hasValue ? value : "--"}
          </span>
          {hasValue && (
            <span
              style={{
                fontSize: "13px",
                fontWeight: 500,
                color: "var(--text-muted)",
              }}
            >
              {unit}
            </span>
          )}
        </div>
        {subtitle && (
          <div
            style={{
              fontSize: "12px",
              color: "var(--text-muted)",
              marginTop: "4px",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Helpers ────────────────────────────────────────────────────

function formatDate(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function formatDisplayDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function minutesToHoursMinutes(mins: number | null | undefined): string {
  if (mins == null) return "--";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}h ${m}m`;
}

function isToday(dateStr: string): boolean {
  return dateStr === formatDate(new Date());
}

// ─── Overview Page ──────────────────────────────────────────────

const API_BASE = "http://localhost:8000/api";

export default function Overview() {
  const [date, setDate] = useState<string>(formatDate(new Date()));
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOverview = useCallback(async (dateStr: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/data/overview?date=${dateStr}`
      );
      if (!resp.ok) {
        const body = await resp.text();
        throw new Error(body || `Request failed: ${resp.statusText}`);
      }
      const json: OverviewResponse = await resp.json();
      setData(json);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load overview data"
      );
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview(date);
  }, [date, fetchOverview]);

  function shiftDate(days: number) {
    const d = new Date(date + "T12:00:00");
    d.setDate(d.getDate() + days);
    const newDate = formatDate(d);
    // Don't allow future dates
    if (newDate <= formatDate(new Date())) {
      setDate(newDate);
    }
  }

  // Extract values from the snake_case API response
  const restingHR = data?.heartRate?.resting_heart_rate ?? null;
  const sleepScore = data?.sleep?.overall_score ?? null;
  const minutesAsleep = data?.sleep?.minutes_asleep ?? null;
  const deepSleepMins = data?.sleep?.deep_sleep_minutes ?? null;
  const remSleepMins = data?.sleep?.rem_sleep_minutes ?? null;
  const steps = data?.activity?.steps ?? null;
  const avgSpo2 = data?.spo2?.avg_spo2 ?? null;
  const minSpo2 = data?.spo2?.min_spo2 ?? null;
  const maxSpo2 = data?.spo2?.max_spo2 ?? null;
  const dailyRmssd = data?.hrv?.daily_rmssd ?? null;
  const breathingRate = data?.breathingRate?.breathing_rate ?? null;
  const skinTemp = data?.skinTemperature?.relative_temp ?? null;
  const vo2Max = data?.vo2Max?.vo2_max ?? null;
  const stressScore = data?.stress?.stress_score ?? null;
  const activeZoneMins = data?.activity?.active_zone_minutes ?? null;
  const caloriesTotal = data?.activity?.calories_total ?? null;

  // Build subtitle text for sleep card
  const sleepSubtitle =
    minutesAsleep != null
      ? `${minutesToHoursMinutes(minutesAsleep)} asleep`
      : undefined;

  const sleepDeepRemSubtitle = (() => {
    const parts: string[] = [];
    if (deepSleepMins != null) parts.push(`Deep: ${deepSleepMins}m`);
    if (remSleepMins != null) parts.push(`REM: ${remSleepMins}m`);
    return parts.length > 0 ? parts.join("  |  ") : undefined;
  })();

  const spo2Subtitle = (() => {
    if (minSpo2 != null && maxSpo2 != null)
      return `Range: ${minSpo2}% - ${maxSpo2}%`;
    if (avgSpo2 != null && avgSpo2 >= 95) return "Normal range";
    if (avgSpo2 != null && avgSpo2 < 95) return "Below typical range";
    return undefined;
  })();

  const stepsSubtitle =
    steps != null && steps >= 10000 ? "Goal reached" : undefined;

  // Count how many metrics have data
  const hasAnyData =
    data &&
    (data.heartRate ||
      data.sleep ||
      data.activity ||
      data.spo2 ||
      data.hrv ||
      data.breathingRate ||
      data.skinTemperature ||
      data.vo2Max ||
      data.stress);

  return (
    <div className="page">
      {/* Page header */}
      <div className="page-header">
        <LayoutDashboard size={24} />
        <h2>Overview</h2>
      </div>

      {/* Date selector */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          marginBottom: "28px",
        }}
      >
        <button
          onClick={() => shiftDate(-1)}
          style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--radius-sm)",
            color: "var(--text-secondary)",
            padding: "8px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--accent)";
            e.currentTarget.style.color = "var(--text-primary)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border-color)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }}
          aria-label="Previous day"
        >
          <ChevronLeft size={18} />
        </button>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--radius-sm)",
            padding: "8px 16px",
            minWidth: "220px",
            justifyContent: "center",
          }}
        >
          <input
            type="date"
            value={date}
            max={formatDate(new Date())}
            onChange={(e) => setDate(e.target.value)}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-primary)",
              fontSize: "14px",
              fontFamily: "inherit",
              fontWeight: 500,
              outline: "none",
              cursor: "pointer",
            }}
          />
          {isToday(date) && (
            <span
              style={{
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--accent)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                background: "var(--accent-dim)",
                padding: "2px 8px",
                borderRadius: "10px",
              }}
            >
              Today
            </span>
          )}
        </div>

        <button
          onClick={() => shiftDate(1)}
          disabled={isToday(date)}
          style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--radius-sm)",
            color: isToday(date)
              ? "var(--text-muted)"
              : "var(--text-secondary)",
            padding: "8px",
            cursor: isToday(date) ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: isToday(date) ? 0.4 : 1,
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            if (!isToday(date)) {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.color = "var(--text-primary)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border-color)";
            e.currentTarget.style.color = isToday(date)
              ? "var(--text-muted)"
              : "var(--text-secondary)";
          }}
          aria-label="Next day"
        >
          <ChevronRight size={18} />
        </button>

        <span
          style={{
            fontSize: "13px",
            color: "var(--text-muted)",
            marginLeft: "4px",
          }}
        >
          {formatDisplayDate(date)}
        </span>
      </div>

      {/* Loading state */}
      {loading && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "80px 0",
            gap: "16px",
          }}
        >
          <Loader2
            size={32}
            className="spin"
            style={{ color: "var(--accent)" }}
          />
          <span style={{ color: "var(--text-muted)", fontSize: "14px" }}>
            Loading health data...
          </span>
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <div
          style={{
            background: "var(--error-dim)",
            border: "1px solid rgba(248, 113, 113, 0.3)",
            borderRadius: "var(--radius)",
            padding: "24px",
            display: "flex",
            alignItems: "flex-start",
            gap: "12px",
          }}
        >
          <AlertCircle
            size={20}
            style={{ color: "var(--error)", flexShrink: 0, marginTop: "1px" }}
          />
          <div>
            <div
              style={{
                color: "var(--error)",
                fontWeight: 600,
                fontSize: "14px",
                marginBottom: "4px",
              }}
            >
              Failed to load overview
            </div>
            <div
              style={{
                color: "var(--text-secondary)",
                fontSize: "13px",
              }}
            >
              {error}
            </div>
            <button
              onClick={() => fetchOverview(date)}
              style={{
                marginTop: "12px",
                background: "transparent",
                border: "1px solid var(--error)",
                borderRadius: "var(--radius-sm)",
                color: "var(--error)",
                padding: "6px 16px",
                fontSize: "13px",
                fontWeight: 500,
                fontFamily: "inherit",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--error-dim)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Empty state (no data for this date) */}
      {!loading && !error && !hasAnyData && (
        <div className="placeholder-card">
          <p>No data available for {formatDisplayDate(date)}.</p>
          <p className="placeholder-sub">
            Try selecting a different date, or upload your Fitbit export in
            Settings.
          </p>
        </div>
      )}

      {/* Metric cards grid */}
      {!loading && !error && hasAnyData && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
            gap: "16px",
          }}
        >
          <MetricCard
            icon={<Heart size={18} />}
            label="Resting Heart Rate"
            value={restingHR}
            unit="bpm"
            statusKey="restingHR"
            rawValue={restingHR}
          />

          <MetricCard
            icon={<Moon size={18} />}
            label="Sleep Score"
            value={sleepScore}
            unit="/ 100"
            statusKey="sleepScore"
            rawValue={sleepScore}
            subtitle={
              sleepSubtitle && sleepDeepRemSubtitle
                ? `${sleepSubtitle}  |  ${sleepDeepRemSubtitle}`
                : sleepSubtitle || sleepDeepRemSubtitle
            }
          />

          <MetricCard
            icon={<Footprints size={18} />}
            label="Steps"
            value={steps != null ? steps.toLocaleString() : null}
            unit="steps"
            statusKey="steps"
            rawValue={steps}
            subtitle={stepsSubtitle}
          />

          <MetricCard
            icon={<Droplets size={18} />}
            label="SpO2"
            value={avgSpo2 != null ? avgSpo2.toFixed(1) : null}
            unit="%"
            statusKey="spo2"
            rawValue={avgSpo2}
            subtitle={spo2Subtitle}
          />

          <MetricCard
            icon={<Activity size={18} />}
            label="HRV"
            value={dailyRmssd != null ? dailyRmssd.toFixed(1) : null}
            unit="ms"
            statusKey="hrv"
            rawValue={dailyRmssd}
            subtitle="RMSSD"
          />

          <MetricCard
            icon={<Wind size={18} />}
            label="Breathing Rate"
            value={breathingRate != null ? breathingRate.toFixed(1) : null}
            unit="br/min"
            statusKey="breathingRate"
            rawValue={breathingRate}
            subtitle="Breaths per minute"
          />

          <MetricCard
            icon={<Thermometer size={18} />}
            label="Skin Temperature"
            value={
              skinTemp != null
                ? `${skinTemp >= 0 ? "+" : ""}${skinTemp.toFixed(1)}`
                : null
            }
            unit="°C"
            statusKey="skinTemp"
            rawValue={skinTemp}
            subtitle="Deviation from baseline"
          />

          <MetricCard
            icon={<TrendingUp size={18} />}
            label="VO2 Max"
            value={vo2Max != null ? vo2Max.toFixed(1) : null}
            unit="mL/kg/min"
            statusKey="vo2max"
            rawValue={vo2Max}
            subtitle="Cardio fitness level"
          />

          <MetricCard
            icon={<Brain size={18} />}
            label="Stress Score"
            value={stressScore}
            unit="/ 100"
            statusKey="stress"
            rawValue={stressScore}
            subtitle={
              stressScore != null && stressScore >= 70
                ? "Body is coping well"
                : stressScore != null && stressScore >= 40
                  ? "Moderate stress response"
                  : stressScore != null
                    ? "Elevated stress response"
                    : undefined
            }
          />

          <MetricCard
            icon={<Timer size={18} />}
            label="Active Zone Minutes"
            value={activeZoneMins}
            unit="min"
            statusKey="activeZone"
            rawValue={activeZoneMins}
            subtitle="Weekly goal: 150 min"
          />

          <MetricCard
            icon={<Flame size={18} />}
            label="Calories"
            value={
              caloriesTotal != null
                ? caloriesTotal.toLocaleString()
                : null
            }
            unit="kcal"
            statusKey="calories"
            rawValue={caloriesTotal}
            subtitle="Total burn"
          />
        </div>
      )}
    </div>
  );
}
