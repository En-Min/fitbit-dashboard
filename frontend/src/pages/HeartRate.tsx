import { useState, useEffect, useMemo, useCallback } from "react";
import { format, subDays } from "date-fns";
import { Heart } from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
  Legend,
  Area,
  ComposedChart,
} from "recharts";
import DateRangePicker from "../components/DateRangePicker";
import { ChartModal, ExpandButton } from "../components/ChartModal";
import {
  spansMultipleYears,
  formatDateLabel,
  calculateTickInterval,
} from "../utils/dateFormat";
import type {
  HeartRateReading,
  HeartRateDaily,
  HRVDaily,
} from "../types/index";

const API_BASE = "http://localhost:8000";

const COLORS = {
  accent: "#00B0B9",
  peak: "#F44336",
  cardio: "#FF9800",
  fatBurn: "#4CAF50",
  restZone: "#64B5F6",
  resting: "#AB47BC",
  deepRmssd: "#FF7043",
};

// --- Downsampling utility ---------------------------------------------------

function downsample<T>(data: T[], maxPoints: number): T[] {
  if (data.length <= maxPoints) return data;
  const factor = Math.ceil(data.length / maxPoints);
  return data.filter((_, i) => i % factor === 0);
}

// --- Helpers ----------------------------------------------------------------

function parseTime(timestamp: string): string {
  // Accept ISO or "HH:MM:SS" — return "HH:MM"
  if (timestamp.includes("T")) {
    return timestamp.split("T")[1]?.substring(0, 5) ?? timestamp;
  }
  return timestamp.substring(0, 5);
}

function bpmZoneColor(bpm: number): string {
  if (bpm < 60) return COLORS.restZone;
  if (bpm < 100) return COLORS.fatBurn;
  if (bpm < 140) return COLORS.cardio;
  return COLORS.peak;
}

// --- Custom tooltip ---------------------------------------------------------

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
  unit?: string;
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: "#1a1d27",
        border: "1px solid #2e3348",
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: 13,
      }}
    >
      <div style={{ color: "#9398ab", marginBottom: 6 }}>{label}</div>
      {payload.map((entry, i) => (
        <div
          key={i}
          style={{
            color: entry.color,
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <span>{entry.name}</span>
          <strong>
            {typeof entry.value === "number"
              ? entry.value.toFixed(1)
              : entry.value}
            {entry.unit ?? ""}
          </strong>
        </div>
      ))}
    </div>
  );
}

// --- Loading spinner --------------------------------------------------------

function LoadingOverlay({ message }: { message: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        padding: "40px 0",
        color: "#9398ab",
        fontSize: 14,
      }}
    >
      <svg
        className="spin"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
      </svg>
      {message}
    </div>
  );
}

// --- Empty state ------------------------------------------------------------

function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "40px 0",
        color: "#606580",
        fontSize: 14,
      }}
    >
      {message}
    </div>
  );
}

// --- Intraday gradient definitions ------------------------------------------

function IntradayGradient() {
  return (
    <defs>
      <linearGradient id="hrGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={COLORS.peak} stopOpacity={0.3} />
        <stop offset="40%" stopColor={COLORS.cardio} stopOpacity={0.15} />
        <stop offset="70%" stopColor={COLORS.fatBurn} stopOpacity={0.1} />
        <stop offset="100%" stopColor={COLORS.restZone} stopOpacity={0.05} />
      </linearGradient>
    </defs>
  );
}

// --- Custom dot for intraday chart ------------------------------------------

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: { bpm: number };
}

function ZoneColorDot({ cx, cy, payload }: DotProps) {
  if (cx == null || cy == null || !payload) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={2}
      fill={bpmZoneColor(payload.bpm)}
      stroke="none"
    />
  );
}

// --- Trend line calculation -------------------------------------------------

function linearRegression(data: { x: number; y: number }[]): {
  slope: number;
  intercept: number;
} {
  const n = data.length;
  if (n < 2) return { slope: 0, intercept: data[0]?.y ?? 0 };
  const sumX = data.reduce((s, d) => s + d.x, 0);
  const sumY = data.reduce((s, d) => s + d.y, 0);
  const sumXY = data.reduce((s, d) => s + d.x * d.y, 0);
  const sumX2 = data.reduce((s, d) => s + d.x * d.x, 0);
  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return { slope: 0, intercept: sumY / n };
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

// ============================================================================
// Main component
// ============================================================================

export default function HeartRate() {
  const today = format(new Date(), "yyyy-MM-dd");
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 30), "yyyy-MM-dd"));
  const [endDate, setEndDate] = useState(today);
  const [selectedDay, setSelectedDay] = useState(today);

  // Data state
  const [intradayHR, setIntradayHR] = useState<HeartRateReading[]>([]);
  const [dailyHR, setDailyHR] = useState<HeartRateDaily[]>([]);
  const [hrvDaily, setHrvDaily] = useState<HRVDaily[]>([]);

  // Loading states
  const [loadingIntraday, setLoadingIntraday] = useState(false);
  const [loadingDaily, setLoadingDaily] = useState(false);
  const [loadingHRV, setLoadingHRV] = useState(false);

  // Modal state for expanded charts
  const [expandedChart, setExpandedChart] = useState<string | null>(null);

  // --- Date range change handler ---
  const handleDateRangeChange = useCallback((start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
    // Default selected day to end date for intraday view
    setSelectedDay(end);
  }, []);

  // --- Fetch intraday HR for selected day ---
  useEffect(() => {
    let cancelled = false;
    async function fetchIntraday() {
      setLoadingIntraday(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/data/heart-rate/intraday?date=${selectedDay}`
        );
        if (!res.ok) throw new Error("Failed to fetch intraday HR");
        const json = await res.json();
        if (!cancelled) {
          setIntradayHR(json.data ?? []);
        }
      } catch {
        if (!cancelled) setIntradayHR([]);
      } finally {
        if (!cancelled) setLoadingIntraday(false);
      }
    }
    fetchIntraday();
    return () => {
      cancelled = true;
    };
  }, [selectedDay]);

  // --- Fetch daily HR and HRV for range ---
  useEffect(() => {
    let cancelled = false;

    async function fetchDaily() {
      setLoadingDaily(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/data/heart-rate/daily?start=${startDate}&end=${endDate}`
        );
        if (!res.ok) throw new Error("Failed to fetch daily HR");
        const json = await res.json();
        if (!cancelled) setDailyHR(json.data ?? []);
      } catch {
        if (!cancelled) setDailyHR([]);
      } finally {
        if (!cancelled) setLoadingDaily(false);
      }
    }

    async function fetchHRV() {
      setLoadingHRV(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/data/hrv?start=${startDate}&end=${endDate}`
        );
        if (!res.ok) throw new Error("Failed to fetch HRV");
        const json = await res.json();
        if (!cancelled) setHrvDaily(json.data ?? []);
      } catch {
        if (!cancelled) setHrvDaily([]);
      } finally {
        if (!cancelled) setLoadingHRV(false);
      }
    }

    fetchDaily();
    fetchHRV();

    return () => {
      cancelled = true;
    };
  }, [startDate, endDate]);

  // --- Derived data: downsampled intraday ---
  const intradayChartData = useMemo(() => {
    const sampled = downsample(intradayHR, 2000);
    return sampled.map((d) => ({
      time: parseTime(d.timestamp),
      bpm: d.bpm,
    }));
  }, [intradayHR]);

  // --- Derived: resting HR for reference line ---
  const restingHR = useMemo(() => {
    const todayEntry = dailyHR.find((d) => d.date === selectedDay);
    return todayEntry?.restingHeartRate ?? null;
  }, [dailyHR, selectedDay]);

  // Detect if date range spans multiple years
  const dateList = useMemo(() => dailyHR.map((d) => d.date), [dailyHR]);
  const needsYear = useMemo(() => spansMultipleYears(dateList), [dateList]);

  // --- Derived: resting HR trend with linear regression line ---
  const restingHRTrendData = useMemo(() => {
    const filtered = dailyHR.filter(
      (d) => d.restingHeartRate != null && d.restingHeartRate > 0
    );
    if (filtered.length === 0) return [];

    const regression = linearRegression(
      filtered.map((d, i) => ({ x: i, y: d.restingHeartRate }))
    );

    return filtered.map((d, i) => ({
      date: d.date,
      dateLabel: formatDateLabel(d.date, needsYear),
      restingHR: d.restingHeartRate,
      trend: Math.round((regression.slope * i + regression.intercept) * 10) / 10,
    }));
  }, [dailyHR, needsYear]);

  // --- Derived: zone data for bar chart ---
  const zoneChartData = useMemo(() => {
    return dailyHR.map((d) => ({
      date: d.date,
      dateLabel: formatDateLabel(d.date, needsYear),
      fatBurn: d.fatBurnMinutes,
      cardio: d.cardioMinutes,
      peak: d.peakMinutes,
    }));
  }, [dailyHR, needsYear]);

  // --- Derived: HRV trend data ---
  const hrvChartData = useMemo(() => {
    return hrvDaily.map((d) => ({
      date: d.date,
      dateLabel: formatDateLabel(d.date, needsYear),
      dailyRmssd: d.dailyRmssd,
      deepRmssd: d.deepRmssd ?? null,
    }));
  }, [hrvDaily, needsYear]);

  // --- Compute intraday XAxis tick interval ---
  const intradayTickInterval = useMemo(() => {
    const len = intradayChartData.length;
    if (len <= 100) return 0;
    // Aim for ~12 ticks across the chart
    return Math.floor(len / 12);
  }, [intradayChartData]);

  return (
    <div className="page">
      {/* Page Header */}
      <div className="page-header">
        <Heart size={24} />
        <h2>Heart Rate</h2>
      </div>

      {/* Date Range Picker */}
      <DateRangePicker
        startDate={startDate}
        endDate={endDate}
        onChange={handleDateRangeChange}
      />

      {/* Day selector for intraday */}
      <div style={{ marginBottom: 24 }}>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: "#9398ab",
            fontSize: 13,
          }}
        >
          Intraday view date:
          <input
            type="date"
            value={selectedDay}
            min={startDate}
            max={endDate}
            onChange={(e) => setSelectedDay(e.target.value)}
            style={{
              background: "#1a1d27",
              border: "1px solid #2e3348",
              borderRadius: 6,
              color: "#e4e6f0",
              padding: "6px 12px",
              fontSize: 13,
              fontFamily: "inherit",
            }}
          />
        </label>
      </div>

      {/* ================================================================ */}
      {/* Section 1: Intraday Heart Rate Timeline                          */}
      {/* ================================================================ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <Heart size={18} />
          <h3>Intraday Heart Rate</h3>
        </div>
        <p className="card-description">
          Per-second / per-5-second heart rate for {selectedDay}. Color zones:
          blue (&lt;60), green (60-100), yellow (100-140), red (&gt;140).
        </p>

        {loadingIntraday ? (
          <LoadingOverlay message="Loading intraday heart rate..." />
        ) : intradayChartData.length === 0 ? (
          <EmptyState message="No intraday heart rate data available for this date." />
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart
              data={intradayChartData}
              margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
            >
              <IntradayGradient />
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2e3348"
                vertical={false}
              />
              <XAxis
                dataKey="time"
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                interval={intradayTickInterval}
              />
              <YAxis
                domain={["dataMin - 5", "dataMax + 5"]}
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                label={{
                  value: "BPM",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "#606580", fontSize: 12 },
                }}
              />
              <Tooltip content={<ChartTooltip />} />

              {/* Zone reference bands */}
              <ReferenceLine
                y={60}
                stroke={COLORS.restZone}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
              />
              <ReferenceLine
                y={100}
                stroke={COLORS.fatBurn}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
              />
              <ReferenceLine
                y={140}
                stroke={COLORS.cardio}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
              />

              {/* Resting HR reference */}
              {restingHR != null && (
                <ReferenceLine
                  y={restingHR}
                  stroke={COLORS.resting}
                  strokeDasharray="8 4"
                  strokeWidth={2}
                  label={{
                    value: `Resting: ${restingHR}`,
                    position: "right",
                    fill: COLORS.resting,
                    fontSize: 11,
                  }}
                />
              )}

              <Area
                type="monotone"
                dataKey="bpm"
                fill="url(#hrGradient)"
                stroke="none"
              />
              <Line
                type="monotone"
                dataKey="bpm"
                stroke={COLORS.accent}
                strokeWidth={1.2}
                dot={false}
                activeDot={<ZoneColorDot />}
                name="BPM"
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ================================================================ */}
      {/* Section 2: Resting Heart Rate Trend                              */}
      {/* ================================================================ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Heart size={18} />
            <h3>Resting Heart Rate Trend</h3>
          </div>
          <ExpandButton onClick={() => setExpandedChart("restingHR")} />
        </div>
        <p className="card-description">
          Daily resting heart rate with a linear trend line over the selected
          range.
        </p>

        {loadingDaily ? (
          <LoadingOverlay message="Loading daily heart rate data..." />
        ) : restingHRTrendData.length === 0 ? (
          <EmptyState message="No resting heart rate data available for this range." />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={restingHRTrendData}
              margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2e3348"
                vertical={false}
              />
              <XAxis
                dataKey="dateLabel"
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                interval={calculateTickInterval(restingHRTrendData.length)}
              />
              <YAxis
                domain={["dataMin - 3", "dataMax + 3"]}
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                label={{
                  value: "BPM",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "#606580", fontSize: 12 },
                }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#9398ab" }}
              />
              <Line
                type="monotone"
                dataKey="restingHR"
                stroke={COLORS.accent}
                strokeWidth={2}
                dot={{ r: 3, fill: COLORS.accent }}
                activeDot={{ r: 5 }}
                name="Resting HR"
              />
              <Line
                type="monotone"
                dataKey="trend"
                stroke={COLORS.resting}
                strokeWidth={1.5}
                strokeDasharray="6 3"
                dot={false}
                name="Trend"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ================================================================ */}
      {/* Section 3: Heart Rate Zones                                      */}
      {/* ================================================================ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Heart size={18} />
            <h3>Heart Rate Zones</h3>
          </div>
          <ExpandButton onClick={() => setExpandedChart("zones")} />
        </div>
        <p className="card-description">
          Daily minutes in Fat Burn, Cardio, and Peak zones.
        </p>

        {loadingDaily ? (
          <LoadingOverlay message="Loading zone data..." />
        ) : zoneChartData.length === 0 ? (
          <EmptyState message="No heart rate zone data available for this range." />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={zoneChartData}
              margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2e3348"
                vertical={false}
              />
              <XAxis
                dataKey="dateLabel"
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                interval={calculateTickInterval(zoneChartData.length)}
              />
              <YAxis
                domain={[0, "auto"]}
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                label={{
                  value: "Minutes",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "#606580", fontSize: 12 },
                }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#9398ab" }}
              />
              <Bar
                dataKey="fatBurn"
                fill={COLORS.fatBurn}
                name="Fat Burn"
                stackId="zones"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="cardio"
                fill={COLORS.cardio}
                name="Cardio"
                stackId="zones"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="peak"
                fill={COLORS.peak}
                name="Peak"
                stackId="zones"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ================================================================ */}
      {/* Section 4: HRV Trend                                             */}
      {/* ================================================================ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Heart size={18} />
            <h3>HRV Trend (RMSSD)</h3>
          </div>
          <ExpandButton onClick={() => setExpandedChart("hrv")} />
        </div>
        <p className="card-description">
          Daily RMSSD with deep-sleep RMSSD overlay. Higher HRV generally
          indicates better recovery.
        </p>

        {loadingHRV ? (
          <LoadingOverlay message="Loading HRV data..." />
        ) : hrvChartData.length === 0 ? (
          <EmptyState message="No HRV data available for this range." />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={hrvChartData}
              margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2e3348"
                vertical={false}
              />
              <XAxis
                dataKey="dateLabel"
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                interval={calculateTickInterval(hrvChartData.length)}
              />
              <YAxis
                domain={["dataMin - 5", "dataMax + 5"]}
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                label={{
                  value: "ms",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "#606580", fontSize: 12 },
                }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#9398ab" }}
              />
              <Line
                type="monotone"
                dataKey="dailyRmssd"
                stroke={COLORS.accent}
                strokeWidth={2}
                dot={{ r: 3, fill: COLORS.accent }}
                activeDot={{ r: 5 }}
                name="Daily RMSSD"
              />
              <Line
                type="monotone"
                dataKey="deepRmssd"
                stroke={COLORS.deepRmssd}
                strokeWidth={2}
                strokeDasharray="4 2"
                dot={{ r: 3, fill: COLORS.deepRmssd }}
                activeDot={{ r: 5 }}
                name="Deep Sleep RMSSD"
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Expanded Chart Modals */}
      <ChartModal
        isOpen={expandedChart === "restingHR"}
        onClose={() => setExpandedChart(null)}
        title="Resting Heart Rate Trend"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={restingHRTrendData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2e3348" vertical={false} />
            <XAxis
              dataKey="dateLabel"
              tick={{ fill: "#9398ab", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#2e3348" }}
              interval={calculateTickInterval(restingHRTrendData.length)}
            />
            <YAxis
              domain={["dataMin - 3", "dataMax + 3"]}
              tick={{ fill: "#9398ab", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#2e3348" }}
              label={{ value: "BPM", angle: -90, position: "insideLeft", style: { fill: "#606580" } }}
            />
            <Tooltip content={<ChartTooltip />} />
            <Legend />
            <Line type="monotone" dataKey="restingHR" stroke={COLORS.accent} strokeWidth={2} dot={{ r: 3 }} name="Resting HR" />
            <Line type="monotone" dataKey="trend" stroke={COLORS.resting} strokeWidth={1.5} strokeDasharray="6 3" dot={false} name="Trend" />
          </LineChart>
        </ResponsiveContainer>
      </ChartModal>

      <ChartModal
        isOpen={expandedChart === "zones"}
        onClose={() => setExpandedChart(null)}
        title="Heart Rate Zones"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={zoneChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2e3348" vertical={false} />
            <XAxis
              dataKey="dateLabel"
              tick={{ fill: "#9398ab", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#2e3348" }}
              interval={calculateTickInterval(zoneChartData.length)}
            />
            <YAxis
              domain={[0, "auto"]}
              tick={{ fill: "#9398ab", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#2e3348" }}
              label={{ value: "Minutes", angle: -90, position: "insideLeft", style: { fill: "#606580" } }}
            />
            <Tooltip content={<ChartTooltip />} />
            <Legend />
            <Bar dataKey="fatBurn" fill={COLORS.fatBurn} name="Fat Burn" stackId="zones" />
            <Bar dataKey="cardio" fill={COLORS.cardio} name="Cardio" stackId="zones" />
            <Bar dataKey="peak" fill={COLORS.peak} name="Peak" stackId="zones" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartModal>

      <ChartModal
        isOpen={expandedChart === "hrv"}
        onClose={() => setExpandedChart(null)}
        title="HRV Trend (RMSSD)"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={hrvChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2e3348" vertical={false} />
            <XAxis
              dataKey="dateLabel"
              tick={{ fill: "#9398ab", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#2e3348" }}
              interval={calculateTickInterval(hrvChartData.length)}
            />
            <YAxis
              domain={["dataMin - 5", "dataMax + 5"]}
              tick={{ fill: "#9398ab", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#2e3348" }}
              label={{ value: "ms", angle: -90, position: "insideLeft", style: { fill: "#606580" } }}
            />
            <Tooltip content={<ChartTooltip />} />
            <Legend />
            <Line type="monotone" dataKey="dailyRmssd" stroke={COLORS.accent} strokeWidth={2} dot={{ r: 3 }} name="Daily RMSSD" />
            <Line type="monotone" dataKey="deepRmssd" stroke={COLORS.deepRmssd} strokeWidth={2} strokeDasharray="4 2" dot={{ r: 3 }} name="Deep Sleep RMSSD" connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </ChartModal>
    </div>
  );
}
