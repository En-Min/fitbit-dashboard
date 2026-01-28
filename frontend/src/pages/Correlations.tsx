import { useState, useEffect, useCallback, useMemo } from "react";
import { format, subDays } from "date-fns";
import { BarChart3 } from "lucide-react";
import {
  ScatterChart,
  Scatter,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ZAxis,
  Legend,
} from "recharts";
import DateRangePicker from "../components/DateRangePicker";

/* ------------------------------------------------------------------ */
/*  Constants & types                                                  */
/* ------------------------------------------------------------------ */

const API_BASE = "http://localhost:8000";

const METRIC_LABELS: Record<string, string> = {
  resting_hr: "Resting Heart Rate (bpm)",
  hrv: "HRV RMSSD (ms)",
  spo2: "SpO2 (%)",
  breathing_rate: "Breathing Rate (br/min)",
  skin_temp: "Skin Temperature (\u00b0C)",
  vo2_max: "VO2 Max (mL/kg/min)",
  sleep_score: "Sleep Score",
  sleep_efficiency: "Sleep Efficiency (%)",
  sleep_duration: "Sleep Duration (min)",
  deep_sleep: "Deep Sleep (min)",
  rem_sleep: "REM Sleep (min)",
  steps: "Steps",
  calories: "Calories",
  active_minutes: "Very Active Minutes",
  active_zone_minutes: "Active Zone Minutes",
  stress: "Stress Score",
};

const ALL_METRICS = Object.keys(METRIC_LABELS);

interface CorrelationPoint {
  date: string;
  x: number;
  y: number;
}

interface CorrelationResponse {
  xMetric: string;
  yMetric: string;
  correlation: number;
  points: CorrelationPoint[];
  availableMetrics: string[];
}

interface SuggestedPair {
  label: string;
  x: string;
  y: string;
}

const SUGGESTED_PAIRS: SuggestedPair[] = [
  { label: "Sleep Score vs Next-Day Resting HR", x: "sleep_score", y: "resting_hr" },
  { label: "HRV vs Stress Score", x: "hrv", y: "stress" },
  { label: "Steps vs Sleep Quality", x: "steps", y: "sleep_score" },
  { label: "Deep Sleep vs HRV", x: "deep_sleep", y: "hrv" },
  { label: "VO2 Max vs Active Zone Minutes", x: "vo2_max", y: "active_zone_minutes" },
  { label: "Skin Temp vs Sleep Score", x: "skin_temp", y: "sleep_score" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function interpretCorrelation(r: number): { strength: string; direction: string } {
  const abs = Math.abs(r);
  let strength: string;
  if (abs > 0.7) strength = "Strong correlation";
  else if (abs > 0.4) strength = "Moderate correlation";
  else if (abs > 0.2) strength = "Weak correlation";
  else strength = "No significant correlation";

  const direction = r >= 0 ? "positive" : "negative";
  return { strength, direction };
}

function correlationColor(r: number): string {
  const abs = Math.abs(r);
  if (abs > 0.7) return "var(--success)";
  if (abs > 0.4) return "var(--warning)";
  if (abs > 0.2) return "var(--text-secondary)";
  return "var(--text-muted)";
}

/** Simple linear regression for the trend line */
function linearRegression(points: CorrelationPoint[]): { slope: number; intercept: number } | null {
  if (points.length < 2) return null;
  const n = points.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  for (const p of points) {
    sumX += p.x;
    sumY += p.y;
    sumXY += p.x * p.y;
    sumX2 += p.x * p.x;
  }
  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

function shortLabel(metric: string): string {
  const full = METRIC_LABELS[metric] ?? metric;
  // Strip the unit in parentheses for axis brevity
  return full.replace(/\s*\(.*?\)\s*$/, "");
}

/* ------------------------------------------------------------------ */
/*  Custom Tooltip components                                          */
/* ------------------------------------------------------------------ */

function ScatterTooltip({ active, payload, xMetric, yMetric }: any) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload;
  if (!data) return null;
  return (
    <div style={tooltipStyle}>
      <div style={{ marginBottom: 4, color: "var(--text-muted)", fontSize: 12 }}>{data.date}</div>
      <div style={{ color: "var(--accent)" }}>
        {shortLabel(xMetric)}: <strong>{data.x}</strong>
      </div>
      <div style={{ color: "#a78bfa" }}>
        {shortLabel(yMetric)}: <strong>{data.y}</strong>
      </div>
    </div>
  );
}

function TimeTooltip({ active, payload, label, xMetric, yMetric }: any) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div style={tooltipStyle}>
      <div style={{ marginBottom: 4, color: "var(--text-muted)", fontSize: 12 }}>{label}</div>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} style={{ color: entry.color }}>
          {entry.dataKey === "x" ? shortLabel(xMetric) : shortLabel(yMetric)}:{" "}
          <strong>{entry.value}</strong>
        </div>
      ))}
    </div>
  );
}

const tooltipStyle: React.CSSProperties = {
  background: "var(--bg-tertiary)",
  border: "1px solid var(--border-color)",
  borderRadius: "var(--radius-sm)",
  padding: "10px 14px",
  fontSize: 13,
  lineHeight: 1.5,
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function Correlations() {
  const today = format(new Date(), "yyyy-MM-dd");
  const ninetyAgo = format(subDays(new Date(), 90), "yyyy-MM-dd");

  const [startDate, setStartDate] = useState(ninetyAgo);
  const [endDate, setEndDate] = useState(today);
  const [xMetric, setXMetric] = useState("sleep_score");
  const [yMetric, setYMetric] = useState("resting_hr");
  const [data, setData] = useState<CorrelationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Fetch data --------------------------------------------------- */

  const fetchCorrelation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        x: xMetric,
        y: yMetric,
        start: startDate,
        end: endDate,
      });
      const res = await fetch(`${API_BASE}/api/data/correlations?${params}`);
      if (!res.ok) throw new Error(`Server responded ${res.status}`);
      const json: CorrelationResponse = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message ?? "Failed to fetch correlation data");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [xMetric, yMetric, startDate, endDate]);

  useEffect(() => {
    fetchCorrelation();
  }, [fetchCorrelation]);

  /* Trend line data ---------------------------------------------- */

  const trendLineData = useMemo(() => {
    if (!data || data.points.length < 2) return [];
    const reg = linearRegression(data.points);
    if (!reg) return [];
    const xs = data.points.map((p) => p.x);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    return [
      { x: minX, y: reg.slope * minX + reg.intercept },
      { x: maxX, y: reg.slope * maxX + reg.intercept },
    ];
  }, [data]);

  /* Handlers ----------------------------------------------------- */

  const handleDateChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
  };

  const handleSuggestionClick = (pair: SuggestedPair) => {
    setXMetric(pair.x);
    setYMetric(pair.y);
  };

  /* Interpretation ------------------------------------------------ */

  const correlation = data?.correlation ?? 0;
  const { strength, direction } = interpretCorrelation(correlation);

  /* Render ------------------------------------------------------- */

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <BarChart3 size={24} />
        <h2>Correlations &amp; Custom Analysis</h2>
      </div>

      {/* Date Range */}
      <DateRangePicker startDate={startDate} endDate={endDate} onChange={handleDateChange} />

      {/* Metric Selectors */}
      <div style={selectorRowStyle}>
        <div style={selectorGroupStyle}>
          <label style={selectorLabelStyle}>X-Axis Metric</label>
          <select
            value={xMetric}
            onChange={(e) => setXMetric(e.target.value)}
            style={selectStyle}
          >
            {ALL_METRICS.map((m) => (
              <option key={m} value={m}>
                {METRIC_LABELS[m]}
              </option>
            ))}
          </select>
        </div>
        <div style={selectorGroupStyle}>
          <label style={selectorLabelStyle}>Y-Axis Metric</label>
          <select
            value={yMetric}
            onChange={(e) => setYMetric(e.target.value)}
            style={selectStyle}
          >
            {ALL_METRICS.map((m) => (
              <option key={m} value={m}>
                {METRIC_LABELS[m]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading / Error */}
      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
          <div className="spin" style={{ display: "inline-block", width: 24, height: 24, border: "3px solid var(--border-color)", borderTopColor: "var(--accent)", borderRadius: "50%" }} />
          <p style={{ marginTop: 12 }}>Loading correlation data...</p>
        </div>
      )}

      {error && (
        <div className="status-message error" style={{ marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Scatter Plot Card */}
      {!loading && data && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <BarChart3 size={18} />
            <h3>
              {shortLabel(xMetric)} vs {shortLabel(yMetric)}
            </h3>
          </div>

          {/* Correlation Badge */}
          <div style={correlationBadgeContainerStyle}>
            <div
              style={{
                ...correlationBadgeStyle,
                background: correlationColor(correlation),
                color: "#fff",
              }}
            >
              r = {correlation.toFixed(3)}
            </div>
            <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>
              {strength} &mdash;{" "}
              <span style={{ textTransform: "capitalize" }}>{direction}</span>
            </span>
          </div>

          {data.points.length === 0 ? (
            <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 30 }}>
              No overlapping data points for these metrics in the selected range.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={400}>
              <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name={shortLabel(xMetric)}
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  stroke="var(--border-color)"
                  label={{
                    value: METRIC_LABELS[xMetric],
                    position: "insideBottom",
                    offset: -10,
                    fill: "var(--text-muted)",
                    fontSize: 12,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name={shortLabel(yMetric)}
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  stroke="var(--border-color)"
                  label={{
                    value: METRIC_LABELS[yMetric],
                    angle: -90,
                    position: "insideLeft",
                    offset: 10,
                    fill: "var(--text-muted)",
                    fontSize: 12,
                    style: { textAnchor: "middle" },
                  }}
                />
                <ZAxis range={[48, 48]} />
                <Tooltip
                  content={<ScatterTooltip xMetric={xMetric} yMetric={yMetric} />}
                  cursor={{ strokeDasharray: "3 3", stroke: "var(--text-muted)" }}
                />
                {/* Data points */}
                <Scatter
                  name="Data Points"
                  data={data.points}
                  fill="var(--accent)"
                  fillOpacity={0.7}
                />
                {/* Trend line */}
                {trendLineData.length === 2 && (
                  <Scatter
                    name="Trend Line"
                    data={trendLineData}
                    fill="none"
                    line={{ stroke: "#a78bfa", strokeWidth: 2, strokeDasharray: "6 3" }}
                    legendType="line"
                    shape={() => null}
                  />
                )}
              </ScatterChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Time Series Overlay Card */}
      {!loading && data && data.points.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <BarChart3 size={18} />
            <h3>Time Series Overlay</h3>
          </div>
          <p className="card-description">
            Both metrics plotted over time with dual Y-axes to reveal temporal patterns.
          </p>

          <ResponsiveContainer width="100%" height={320}>
            <LineChart
              data={data.points}
              margin={{ top: 10, right: 30, bottom: 10, left: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis
                dataKey="date"
                tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
                stroke="var(--border-color)"
                tickFormatter={(val: string) => {
                  if (!val) return "";
                  const parts = val.split("-");
                  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : val;
                }}
              />
              <YAxis
                yAxisId="left"
                tick={{ fill: "var(--accent)", fontSize: 11 }}
                stroke="var(--accent)"
                label={{
                  value: shortLabel(xMetric),
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--accent)",
                  fontSize: 11,
                  style: { textAnchor: "middle" },
                }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fill: "#a78bfa", fontSize: 11 }}
                stroke="#a78bfa"
                label={{
                  value: shortLabel(yMetric),
                  angle: 90,
                  position: "insideRight",
                  fill: "#a78bfa",
                  fontSize: 11,
                  style: { textAnchor: "middle" },
                }}
              />
              <Tooltip
                content={<TimeTooltip xMetric={xMetric} yMetric={yMetric} />}
                cursor={{ stroke: "var(--text-muted)", strokeDasharray: "3 3" }}
              />
              <Legend
                formatter={(value: string) =>
                  value === "x" ? shortLabel(xMetric) : shortLabel(yMetric)
                }
                wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="x"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                name="x"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="y"
                stroke="#a78bfa"
                strokeWidth={2}
                dot={false}
                name="y"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Suggested Correlations */}
      <div className="card">
        <div className="card-header">
          <BarChart3 size={18} />
          <h3>Suggested Correlations</h3>
        </div>
        <p className="card-description">
          Click a card to explore a commonly interesting metric pair.
        </p>

        <div style={suggestionsGridStyle}>
          {SUGGESTED_PAIRS.map((pair) => {
            const isActive = xMetric === pair.x && yMetric === pair.y;
            return (
              <button
                key={pair.label}
                onClick={() => handleSuggestionClick(pair)}
                style={{
                  ...suggestionCardStyle,
                  borderColor: isActive ? "var(--accent)" : "var(--border-color)",
                  background: isActive ? "var(--accent-dim)" : "var(--bg-tertiary)",
                }}
              >
                <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6, display: "block" }}>
                  {pair.label}
                </span>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  {shortLabel(pair.x)} &harr; {shortLabel(pair.y)}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Inline styles (keeps CSS scoped; consistent with dark theme vars) */
/* ------------------------------------------------------------------ */

const selectorRowStyle: React.CSSProperties = {
  display: "flex",
  gap: 16,
  flexWrap: "wrap",
  marginBottom: 24,
};

const selectorGroupStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
  flex: "1 1 220px",
  minWidth: 200,
};

const selectorLabelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const selectStyle: React.CSSProperties = {
  appearance: "none",
  WebkitAppearance: "none",
  background: "var(--bg-secondary)",
  border: "1px solid var(--border-color)",
  borderRadius: "var(--radius-sm)",
  color: "var(--text-primary)",
  fontSize: 14,
  fontFamily: "inherit",
  padding: "10px 14px",
  cursor: "pointer",
  outline: "none",
  backgroundImage:
    'url("data:image/svg+xml,%3Csvg width=\'10\' height=\'6\' viewBox=\'0 0 10 6\' fill=\'none\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M1 1L5 5L9 1\' stroke=\'%239398ab\' stroke-width=\'1.5\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E")',
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 12px center",
  paddingRight: 36,
};

const correlationBadgeContainerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 14,
  marginBottom: 16,
  flexWrap: "wrap",
};

const correlationBadgeStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "6px 16px",
  borderRadius: 20,
  fontWeight: 700,
  fontSize: 15,
  letterSpacing: "0.02em",
  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
};

const suggestionsGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
  gap: 12,
};

const suggestionCardStyle: React.CSSProperties = {
  border: "1px solid var(--border-color)",
  borderRadius: "var(--radius-sm)",
  padding: "16px 18px",
  cursor: "pointer",
  textAlign: "left",
  fontFamily: "inherit",
  transition: "all 0.15s ease",
};
