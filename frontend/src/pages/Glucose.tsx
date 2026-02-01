import { useState, useEffect, useMemo } from "react";
import { format, subDays } from "date-fns";
import { Droplet } from "lucide-react";
import {
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  ReferenceArea,
  Legend,
  ComposedChart,
} from "recharts";
import DateRangePicker from "../components/DateRangePicker";

/* ------------------------------------------------------------------ */
/*  Constants & types                                                  */
/* ------------------------------------------------------------------ */

const API_BASE = "http://localhost:8000";

const COLORS = {
  accent: "#00B0B9",
  inRange: "#4CAF50",
  low: "#FF9800",
  high: "#F44336",
  targetBg: "rgba(76, 175, 80, 0.1)",
  p10p90: "rgba(255, 152, 0, 0.2)",
  p25p75: "rgba(0, 176, 185, 0.3)",
  median: "#00B0B9",
};

interface GlucoseReading {
  timestamp: string;
  value: number;
  source: string;
}

interface TimeInRange {
  total_readings: number;
  in_range_percent: number;
  low_percent: number;
  high_percent: number;
  very_low_percent: number;
  very_high_percent: number;
}

interface AGPHourly {
  hour: number;
  p10: number | null;
  p25: number | null;
  median: number | null;
  p75: number | null;
  p90: number | null;
  count: number;
}

interface AGPData {
  start_date: string;
  end_date: string;
  total_readings: number;
  hourly: AGPHourly[];
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatHour(hour: number): string {
  if (hour === 0) return "12am";
  if (hour === 12) return "12pm";
  if (hour < 12) return `${hour}am`;
  return `${hour - 12}pm`;
}

/* ------------------------------------------------------------------ */
/*  Custom Tooltip components                                          */
/* ------------------------------------------------------------------ */

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
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
          <strong>{entry.value} mg/dL</strong>
        </div>
      ))}
    </div>
  );
}

interface AGPTooltipPayloadEntry {
  payload: AGPHourly;
}

function AGPTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: AGPTooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

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
      <div style={{ color: "#9398ab", marginBottom: 6 }}>
        {formatHour(data.hour)} ({data.count} readings)
      </div>
      <div style={{ color: COLORS.high }}>90th: {data.p90 ?? "-"}</div>
      <div style={{ color: COLORS.accent }}>75th: {data.p75 ?? "-"}</div>
      <div style={{ color: COLORS.median, fontWeight: 600 }}>
        Median: {data.median ?? "-"}
      </div>
      <div style={{ color: COLORS.accent }}>25th: {data.p25 ?? "-"}</div>
      <div style={{ color: COLORS.low }}>10th: {data.p10 ?? "-"}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Loading & Empty states                                             */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export default function Glucose() {
  const today = format(new Date(), "yyyy-MM-dd");
  const fourteenAgo = format(subDays(new Date(), 14), "yyyy-MM-dd");

  // State for date range
  const [startDate, setStartDate] = useState(fourteenAgo);
  const [endDate, setEndDate] = useState(today);
  const [selectedDay, setSelectedDay] = useState(today);

  // Data state
  const [readings, setReadings] = useState<GlucoseReading[]>([]);
  const [tir, setTir] = useState<TimeInRange | null>(null);
  const [agp, setAgp] = useState<AGPData | null>(null);

  // Loading states
  const [loadingReadings, setLoadingReadings] = useState(false);
  const [loadingTir, setLoadingTir] = useState(false);
  const [loadingAgp, setLoadingAgp] = useState(false);

  // --- Date range change handler ---
  const handleDateRangeChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
    setSelectedDay(end);
  };

  // --- Fetch readings for selected day ---
  useEffect(() => {
    let cancelled = false;
    async function fetchReadings() {
      setLoadingReadings(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/data/glucose?date=${selectedDay}`
        );
        if (!res.ok) throw new Error("Failed to fetch glucose readings");
        const json = await res.json();
        if (!cancelled) {
          setReadings(json.readings ?? []);
        }
      } catch {
        if (!cancelled) setReadings([]);
      } finally {
        if (!cancelled) setLoadingReadings(false);
      }
    }
    fetchReadings();
    return () => {
      cancelled = true;
    };
  }, [selectedDay]);

  // --- Fetch time in range for date range ---
  useEffect(() => {
    let cancelled = false;
    async function fetchTir() {
      setLoadingTir(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/data/glucose/time-in-range?start=${startDate}&end=${endDate}`
        );
        if (!res.ok) throw new Error("Failed to fetch time in range");
        const json = await res.json();
        if (!cancelled) {
          setTir(json);
        }
      } catch {
        if (!cancelled) setTir(null);
      } finally {
        if (!cancelled) setLoadingTir(false);
      }
    }
    fetchTir();
    return () => {
      cancelled = true;
    };
  }, [startDate, endDate]);

  // --- Fetch AGP for date range ---
  useEffect(() => {
    let cancelled = false;
    async function fetchAgp() {
      setLoadingAgp(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/data/glucose/agp?start=${startDate}&end=${endDate}`
        );
        if (!res.ok) throw new Error("Failed to fetch AGP");
        const json = await res.json();
        if (!cancelled) {
          setAgp(json);
        }
      } catch {
        if (!cancelled) setAgp(null);
      } finally {
        if (!cancelled) setLoadingAgp(false);
      }
    }
    fetchAgp();
    return () => {
      cancelled = true;
    };
  }, [startDate, endDate]);

  // --- Derived data: intraday chart ---
  const intradayChartData = useMemo(() => {
    return readings.map((r) => {
      const time = r.timestamp.includes("T")
        ? r.timestamp.split("T")[1]?.substring(0, 5)
        : r.timestamp.substring(11, 16);
      return {
        time,
        value: r.value,
      };
    });
  }, [readings]);

  // --- Derived data: AGP chart ---
  const agpChartData = useMemo(() => {
    if (!agp) return [];
    return agp.hourly.map((h) => ({
      hour: formatHour(h.hour),
      hourNum: h.hour,
      p10: h.p10,
      p25: h.p25,
      median: h.median,
      p75: h.p75,
      p90: h.p90,
      // For stacked area chart, calculate the differences
      band10_25: h.p25 != null && h.p10 != null ? h.p25 - h.p10 : null,
      band25_median: h.median != null && h.p25 != null ? h.median - h.p25 : null,
      band_median_75: h.p75 != null && h.median != null ? h.p75 - h.median : null,
      band75_90: h.p90 != null && h.p75 != null ? h.p90 - h.p75 : null,
    }));
  }, [agp]);

  return (
    <div className="page">
      {/* Page Header */}
      <div className="page-header">
        <Droplet size={24} />
        <h2>Glucose</h2>
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
          Daily view date:
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
      {/* Section 1: Time in Range Stats                                   */}
      {/* ================================================================ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <Droplet size={18} />
          <h3>Time in Range</h3>
        </div>
        <p className="card-description">
          Percentage of readings within target glucose ranges for the selected
          period.
        </p>

        {loadingTir ? (
          <LoadingOverlay message="Loading time in range..." />
        ) : !tir || tir.total_readings === 0 ? (
          <EmptyState message="No glucose data available for this range." />
        ) : (
          <div
            style={{
              display: "flex",
              gap: 24,
              justifyContent: "center",
              flexWrap: "wrap",
              padding: "20px 0",
            }}
          >
            <div style={statBoxStyle}>
              <span style={{ ...statValueStyle, color: COLORS.inRange }}>
                {tir.in_range_percent}%
              </span>
              <span style={statLabelStyle}>In Range (70-180)</span>
            </div>
            <div style={statBoxStyle}>
              <span style={{ ...statValueStyle, color: COLORS.low }}>
                {tir.low_percent}%
              </span>
              <span style={statLabelStyle}>Low (&lt;70)</span>
            </div>
            <div style={statBoxStyle}>
              <span style={{ ...statValueStyle, color: COLORS.high }}>
                {tir.high_percent}%
              </span>
              <span style={statLabelStyle}>High (&gt;180)</span>
            </div>
            <div style={statBoxStyle}>
              <span style={{ ...statValueStyle, color: "#9398ab" }}>
                {tir.total_readings}
              </span>
              <span style={statLabelStyle}>Total Readings</span>
            </div>
          </div>
        )}
      </div>

      {/* ================================================================ */}
      {/* Section 2: Daily Timeline                                        */}
      {/* ================================================================ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <Droplet size={18} />
          <h3>Daily Timeline</h3>
        </div>
        <p className="card-description">
          Glucose readings throughout {selectedDay}. Green zone indicates target
          range (70-180 mg/dL).
        </p>

        {loadingReadings ? (
          <LoadingOverlay message="Loading glucose readings..." />
        ) : intradayChartData.length === 0 ? (
          <EmptyState message="No glucose data available for this date." />
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart
              data={intradayChartData}
              margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2e3348"
                vertical={false}
              />
              {/* Target range background */}
              <ReferenceArea
                y1={70}
                y2={180}
                fill={COLORS.targetBg}
                fillOpacity={1}
              />
              <ReferenceLine
                y={70}
                stroke={COLORS.low}
                strokeDasharray="4 4"
                strokeOpacity={0.7}
              />
              <ReferenceLine
                y={180}
                stroke={COLORS.high}
                strokeDasharray="4 4"
                strokeOpacity={0.7}
              />
              <XAxis
                dataKey="time"
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                interval={Math.max(0, Math.floor(intradayChartData.length / 12) - 1)}
              />
              <YAxis
                domain={[40, 250]}
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                label={{
                  value: "mg/dL",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "#606580", fontSize: 12 },
                }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Line
                type="monotone"
                dataKey="value"
                stroke={COLORS.accent}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: COLORS.accent }}
                name="Glucose"
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ================================================================ */}
      {/* Section 3: AGP (Ambulatory Glucose Profile)                      */}
      {/* ================================================================ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <Droplet size={18} />
          <h3>Ambulatory Glucose Profile (AGP)</h3>
        </div>
        <p className="card-description">
          Glucose patterns by hour of day, showing median and percentile bands
          (10th-90th) for the selected period.
        </p>

        {loadingAgp ? (
          <LoadingOverlay message="Loading AGP..." />
        ) : !agp || agp.total_readings === 0 ? (
          <EmptyState message="No glucose data available for AGP analysis." />
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart
              data={agpChartData}
              margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2e3348"
                vertical={false}
              />
              {/* Target range reference lines */}
              <ReferenceLine
                y={70}
                stroke={COLORS.low}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
              />
              <ReferenceLine
                y={180}
                stroke={COLORS.high}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
              />
              <XAxis
                dataKey="hour"
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
              />
              <YAxis
                domain={[40, 250]}
                tick={{ fill: "#9398ab", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#2e3348" }}
                label={{
                  value: "mg/dL",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "#606580", fontSize: 12 },
                }}
              />
              <Tooltip content={<AGPTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#9398ab" }}
              />
              {/* P10-P90 band (outer) */}
              <Area
                type="monotone"
                dataKey="p90"
                stroke="none"
                fill={COLORS.p10p90}
                name="90th percentile"
              />
              <Area
                type="monotone"
                dataKey="p10"
                stroke="none"
                fill="#12141c"
                name="10th percentile"
              />
              {/* P25-P75 band (inner) */}
              <Area
                type="monotone"
                dataKey="p75"
                stroke="none"
                fill={COLORS.p25p75}
                name="75th percentile"
              />
              <Area
                type="monotone"
                dataKey="p25"
                stroke="none"
                fill="#12141c"
                name="25th percentile"
              />
              {/* Median line */}
              <Line
                type="monotone"
                dataKey="median"
                stroke={COLORS.median}
                strokeWidth={2}
                dot={false}
                name="Median"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Inline styles                                                      */
/* ------------------------------------------------------------------ */

const statBoxStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: 8,
  padding: "16px 24px",
  background: "var(--bg-tertiary)",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-color)",
  minWidth: 120,
};

const statValueStyle: React.CSSProperties = {
  fontSize: 28,
  fontWeight: 700,
  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
};

const statLabelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#9398ab",
  textAlign: "center",
};
