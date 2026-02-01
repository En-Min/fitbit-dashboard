import { useState, useEffect, useCallback, useMemo } from "react";
import { format, subDays, parseISO } from "date-fns";
import { Moon } from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import DateRangePicker from "../components/DateRangePicker";
import { ChartModal, ExpandButton } from "../components/ChartModal";
import {
  spansMultipleYears,
  formatDateLabel,
  calculateTickInterval,
} from "../utils/dateFormat";
import type { SleepLog, SleepStage } from "../types";

const API_BASE = "http://localhost:8000";

// Stage colors
const STAGE_COLORS = {
  wake: "#E91E63",
  rem: "#9C27B0",
  light: "#2196F3",
  deep: "#1A237E",
} as const;

// Map stage string to a numeric level for the hypnogram (higher = more awake)
const STAGE_LEVEL: Record<string, number> = {
  deep: 0,
  light: 1,
  rem: 2,
  wake: 3,
};

const STAGE_LABELS: Record<number, string> = {
  0: "Deep",
  1: "Light",
  2: "REM",
  3: "Wake",
};

// SpO2 daily shape from the API
interface SpO2Daily {
  date: string;
  avg: number;
  min: number;
  max: number;
}

interface BreathingRateDaily {
  date: string;
  breathingRate: number;
}

interface SkinTempDaily {
  date: string;
  relativeTemp: number;
}

// Hypnogram data point
interface HypnogramPoint {
  time: string;
  timeLabel: string;
  stage: number;
  stageName: string;
}

export default function Sleep() {
  const today = format(new Date(), "yyyy-MM-dd");
  const thirtyDaysAgo = format(subDays(new Date(), 30), "yyyy-MM-dd");

  const [startDate, setStartDate] = useState(thirtyDaysAgo);
  const [endDate, setEndDate] = useState(today);

  const [sleepLogs, setSleepLogs] = useState<SleepLog[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [stages, setStages] = useState<SleepStage[]>([]);
  const [stagesLoading, setStagesLoading] = useState(false);

  const [spo2, setSpo2] = useState<SpO2Daily | null>(null);
  const [breathingRate, setBreathingRate] = useState<BreathingRateDaily | null>(null);
  const [skinTemp, setSkinTemp] = useState<SkinTempDaily | null>(null);
  const [vitalsLoading, setVitalsLoading] = useState(false);

  // Modal states for expanded charts
  const [expandedChart, setExpandedChart] = useState<string | null>(null);

  // Fetch sleep logs for the date range
  const fetchSleepLogs = useCallback(async (start: string, end: string) => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/data/sleep?start=${start}&end=${end}`
      );
      if (!res.ok) throw new Error("Failed to fetch sleep data");
      const json = await res.json();
      const logs: SleepLog[] = json.data ?? [];
      setSleepLogs(logs);

      // Auto-select the most recent night
      if (logs.length > 0) {
        const sorted = [...logs].sort(
          (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
        );
        setSelectedDate(sorted[0].date);
      } else {
        setSelectedDate(null);
      }
    } catch (err) {
      console.error("Sleep fetch error:", err);
      setSleepLogs([]);
      setSelectedDate(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch stages for a specific sleep log
  const fetchStages = useCallback(async (sleepLogId: number) => {
    setStagesLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/data/sleep/stages/${sleepLogId}`
      );
      if (!res.ok) throw new Error("Failed to fetch sleep stages");
      const json = await res.json();
      setStages(json.data ?? []);
    } catch (err) {
      console.error("Stages fetch error:", err);
      setStages([]);
    } finally {
      setStagesLoading(false);
    }
  }, []);

  // Fetch vitals for the selected date
  const fetchVitals = useCallback(async (date: string) => {
    setVitalsLoading(true);
    try {
      const [spo2Res, brRes, stRes] = await Promise.all([
        fetch(`${API_BASE}/api/data/spo2?start=${date}&end=${date}`),
        fetch(`${API_BASE}/api/data/breathing-rate?start=${date}&end=${date}`),
        fetch(`${API_BASE}/api/data/skin-temperature?start=${date}&end=${date}`),
      ]);

      const spo2Json = spo2Res.ok ? await spo2Res.json() : { data: [] };
      const brJson = brRes.ok ? await brRes.json() : { data: [] };
      const stJson = stRes.ok ? await stRes.json() : { data: [] };

      setSpo2(spo2Json.data?.[0] ?? null);
      setBreathingRate(brJson.data?.[0] ?? null);
      setSkinTemp(stJson.data?.[0] ?? null);
    } catch (err) {
      console.error("Vitals fetch error:", err);
      setSpo2(null);
      setBreathingRate(null);
      setSkinTemp(null);
    } finally {
      setVitalsLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchSleepLogs(startDate, endDate);
  }, [startDate, endDate, fetchSleepLogs]);

  // When selectedDate changes, fetch stages and vitals
  useEffect(() => {
    if (!selectedDate) {
      setStages([]);
      setSpo2(null);
      setBreathingRate(null);
      setSkinTemp(null);
      return;
    }

    const log = sleepLogs.find((l) => l.date === selectedDate);
    if (log) {
      fetchStages(log.id);
    } else {
      setStages([]);
    }
    fetchVitals(selectedDate);
  }, [selectedDate, sleepLogs, fetchStages, fetchVitals]);

  const handleDateRangeChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
  };

  // Detect if date range spans multiple years
  const dateList = useMemo(
    () => sleepLogs.map((l) => l.date),
    [sleepLogs]
  );
  const needsYear = useMemo(() => spansMultipleYears(dateList), [dateList]);

  // Sleep Score Trend data
  const scoreTrendData = useMemo(() => {
    return sleepLogs
      .filter((l) => l.overallScore != null)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((l) => ({
        date: l.date,
        dateLabel: formatDateLabel(l.date, needsYear),
        score: l.overallScore,
      }));
  }, [sleepLogs, needsYear]);

  // Duration breakdown data
  const durationData = useMemo(() => {
    return sleepLogs
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((l) => ({
        date: l.date,
        dateLabel: formatDateLabel(l.date, needsYear),
        deep: l.deepSleepMinutes ?? 0,
        rem: l.remSleepMinutes ?? 0,
        light: l.lightSleepMinutes ?? 0,
        awake: l.minutesAwake ?? 0,
      }));
  }, [sleepLogs, needsYear]);

  // Build hypnogram data from stages
  const hypnogramData = useMemo((): HypnogramPoint[] => {
    if (stages.length === 0) return [];

    const sorted = [...stages].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const points: HypnogramPoint[] = [];

    for (const s of sorted) {
      const normalizedStage = s.stage.toLowerCase();
      const level = STAGE_LEVEL[normalizedStage] ?? 3;
      const t = new Date(s.timestamp);
      const timeLabel = format(t, "h:mm a");

      points.push({
        time: s.timestamp,
        timeLabel,
        stage: level,
        stageName:
          normalizedStage.charAt(0).toUpperCase() + normalizedStage.slice(1),
      });

      // Add a point at the end of this stage's duration to create the step effect
      const endTime = new Date(t.getTime() + s.durationSeconds * 1000);
      points.push({
        time: endTime.toISOString(),
        timeLabel: format(endTime, "h:mm a"),
        stage: level,
        stageName:
          normalizedStage.charAt(0).toUpperCase() + normalizedStage.slice(1),
      });
    }

    return points;
  }, [stages]);

  // Handle click on score trend chart to select a date
  const handleScoreClick = (data: any) => {
    if (data?.activePayload?.[0]?.payload?.date) {
      setSelectedDate(data.activePayload[0].payload.date);
    }
  };

  // Handle click on duration chart to select a date
  const handleDurationClick = (data: any) => {
    if (data?.activePayload?.[0]?.payload?.date) {
      setSelectedDate(data.activePayload[0].payload.date);
    }
  };

  const selectedLog = sleepLogs.find((l) => l.date === selectedDate);

  // Color function for the hypnogram area based on stage level
  const getHypnogramColor = (level: number): string => {
    switch (level) {
      case 0:
        return STAGE_COLORS.deep;
      case 1:
        return STAGE_COLORS.light;
      case 2:
        return STAGE_COLORS.rem;
      case 3:
        return STAGE_COLORS.wake;
      default:
        return STAGE_COLORS.light;
    }
  };

  // Custom tooltip for the hypnogram
  const HypnogramTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload as HypnogramPoint;
    return (
      <div
        style={{
          background: "var(--bg-tertiary)",
          border: "1px solid var(--border-color)",
          borderRadius: "var(--radius-sm)",
          padding: "8px 12px",
          fontSize: "13px",
        }}
      >
        <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>
          {d.timeLabel}
        </div>
        <div
          style={{
            color: getHypnogramColor(d.stage),
            fontWeight: 500,
            marginTop: 2,
          }}
        >
          {d.stageName}
        </div>
      </div>
    );
  };

  // Custom tooltip for the score trend
  const ScoreTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div
        style={{
          background: "var(--bg-tertiary)",
          border: "1px solid var(--border-color)",
          borderRadius: "var(--radius-sm)",
          padding: "8px 12px",
          fontSize: "13px",
        }}
      >
        <div style={{ color: "var(--text-secondary)" }}>{d.dateLabel}</div>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginTop: 2 }}>
          Score: {d.score}
        </div>
      </div>
    );
  };

  // Custom tooltip for duration breakdown
  const DurationTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div
        style={{
          background: "var(--bg-tertiary)",
          border: "1px solid var(--border-color)",
          borderRadius: "var(--radius-sm)",
          padding: "8px 12px",
          fontSize: "13px",
        }}
      >
        <div
          style={{
            color: "var(--text-secondary)",
            marginBottom: 4,
            fontWeight: 600,
          }}
        >
          {d.dateLabel}
        </div>
        <div style={{ color: STAGE_COLORS.deep }}>
          Deep: {d.deep} min
        </div>
        <div style={{ color: STAGE_COLORS.rem }}>
          REM: {d.rem} min
        </div>
        <div style={{ color: STAGE_COLORS.light }}>
          Light: {d.light} min
        </div>
        <div style={{ color: STAGE_COLORS.wake }}>
          Awake: {d.awake} min
        </div>
        <div
          style={{
            color: "var(--text-muted)",
            marginTop: 4,
            borderTop: "1px solid var(--border-color)",
            paddingTop: 4,
          }}
        >
          Total: {d.deep + d.rem + d.light + d.awake} min
        </div>
      </div>
    );
  };

  // Hypnogram Y-axis tick formatter
  const stageTickFormatter = (value: number): string => {
    return STAGE_LABELS[value] ?? "";
  };

  // Generate X-axis ticks for hypnogram at 1-hour intervals
  const hypnogramTicks = useMemo(() => {
    if (hypnogramData.length === 0) return [];
    const first = new Date(hypnogramData[0].time).getTime();
    const last = new Date(hypnogramData[hypnogramData.length - 1].time).getTime();
    const ticks: string[] = [];
    // Round first to next full hour
    const startHour = new Date(first);
    startHour.setMinutes(0, 0, 0);
    if (startHour.getTime() < first) {
      startHour.setHours(startHour.getHours() + 1);
    }
    for (let t = startHour.getTime(); t <= last; t += 3600000) {
      ticks.push(new Date(t).toISOString());
    }
    return ticks;
  }, [hypnogramData]);

  const formatHypnogramXAxis = (value: string): string => {
    try {
      return format(new Date(value), "h a");
    } catch {
      return "";
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <Moon size={24} />
        <h2>Sleep Analysis</h2>
      </div>

      <DateRangePicker
        startDate={startDate}
        endDate={endDate}
        onChange={handleDateRangeChange}
      />

      {loading ? (
        <div className="placeholder-card">
          <p>Loading sleep data...</p>
        </div>
      ) : sleepLogs.length === 0 ? (
        <div className="placeholder-card">
          <p>No sleep data available for this date range.</p>
          <p className="placeholder-sub">
            Try selecting a different range or import your Fitbit data.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Sleep Score Trend */}
          <div className="card">
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Moon size={18} />
                <h3>Sleep Score Trend</h3>
              </div>
              <ExpandButton onClick={() => setExpandedChart("score")} />
            </div>
            <p className="card-description">
              Click on a data point to view detailed sleep stages for that
              night.
              {selectedDate && (
                <span style={{ color: "var(--accent)", marginLeft: 8 }}>
                  Selected: {format(parseISO(selectedDate), "MMM d, yyyy")}
                </span>
              )}
            </p>

            {scoreTrendData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart
                  data={scoreTrendData}
                  onClick={handleScoreClick}
                  style={{ cursor: "pointer" }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border-color)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="dateLabel"
                    tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                    axisLine={{ stroke: "var(--border-color)" }}
                    tickLine={false}
                    interval={calculateTickInterval(scoreTrendData.length)}
                  />
                  <YAxis
                    domain={["dataMin - 5", "dataMax + 5"]}
                    tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                    axisLine={{ stroke: "var(--border-color)" }}
                    tickLine={false}
                    width={36}
                  />
                  <Tooltip content={<ScoreTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={(props: any) => {
                      const { cx, cy, payload } = props;
                      const isSelected = payload.date === selectedDate;
                      return (
                        <circle
                          key={`dot-${payload.date}`}
                          cx={cx}
                          cy={cy}
                          r={isSelected ? 6 : 3}
                          fill={isSelected ? "var(--accent)" : "var(--bg-secondary)"}
                          stroke="var(--accent)"
                          strokeWidth={isSelected ? 3 : 2}
                        />
                      );
                    }}
                    activeDot={{
                      r: 5,
                      fill: "var(--accent)",
                      stroke: "var(--bg-secondary)",
                      strokeWidth: 2,
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div
                style={{
                  textAlign: "center",
                  padding: "40px 0",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                No sleep score data available in this range.
              </div>
            )}
          </div>

          {/* Sleep Stage Hypnogram */}
          <div className="card">
            <div className="card-header">
              <Moon size={18} />
              <h3>Sleep Stage Hypnogram</h3>
            </div>
            <p className="card-description">
              {selectedDate
                ? `Night of ${format(parseISO(selectedDate), "MMMM d, yyyy")}`
                : "Select a night from the score trend to view stages."}
              {selectedLog && (
                <span style={{ color: "var(--text-muted)", marginLeft: 12 }}>
                  Efficiency: {selectedLog.efficiency}% | Duration:{" "}
                  {Math.round(selectedLog.durationMs / 60000)} min
                </span>
              )}
            </p>

            {!selectedDate ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "40px 0",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                Click a date on the Sleep Score chart above to view the
                hypnogram.
              </div>
            ) : stagesLoading ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "40px 0",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                Loading sleep stages...
              </div>
            ) : hypnogramData.length === 0 ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "40px 0",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                No stage data available for this night.
              </div>
            ) : (
              <>
                {/* Stage legend */}
                <div
                  style={{
                    display: "flex",
                    gap: 20,
                    marginBottom: 12,
                    flexWrap: "wrap",
                  }}
                >
                  {(["wake", "rem", "light", "deep"] as const).map((s) => (
                    <div
                      key={s}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        fontSize: 12,
                        color: "var(--text-secondary)",
                      }}
                    >
                      <span
                        style={{
                          width: 12,
                          height: 12,
                          borderRadius: 3,
                          background: STAGE_COLORS[s],
                          display: "inline-block",
                        }}
                      />
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </div>
                  ))}
                </div>

                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={hypnogramData}>
                    <defs>
                      <linearGradient
                        id="hypnogramGradient"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor={STAGE_COLORS.wake}
                          stopOpacity={0.6}
                        />
                        <stop
                          offset="33%"
                          stopColor={STAGE_COLORS.rem}
                          stopOpacity={0.6}
                        />
                        <stop
                          offset="66%"
                          stopColor={STAGE_COLORS.light}
                          stopOpacity={0.6}
                        />
                        <stop
                          offset="100%"
                          stopColor={STAGE_COLORS.deep}
                          stopOpacity={0.8}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="var(--border-color)"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="time"
                      ticks={hypnogramTicks}
                      tickFormatter={formatHypnogramXAxis}
                      tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                      axisLine={{ stroke: "var(--border-color)" }}
                      tickLine={false}
                      type="category"
                    />
                    <YAxis
                      domain={[-0.5, 3.5]}
                      ticks={[0, 1, 2, 3]}
                      tickFormatter={stageTickFormatter}
                      tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                      axisLine={{ stroke: "var(--border-color)" }}
                      tickLine={false}
                      width={48}
                      reversed
                    />
                    <Tooltip content={<HypnogramTooltip />} />
                    <Area
                      type="stepAfter"
                      dataKey="stage"
                      stroke={STAGE_COLORS.rem}
                      strokeWidth={1.5}
                      fill="url(#hypnogramGradient)"
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </>
            )}
          </div>

          {/* Sleep Duration Breakdown */}
          <div className="card">
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Moon size={18} />
                <h3>Sleep Duration Breakdown</h3>
              </div>
              <ExpandButton onClick={() => setExpandedChart("duration")} />
            </div>
            <p className="card-description">
              Nightly sleep stage composition. Click a bar to select that night.
            </p>

            {durationData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={durationData}
                  onClick={handleDurationClick}
                  style={{ cursor: "pointer" }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border-color)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="dateLabel"
                    tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                    axisLine={{ stroke: "var(--border-color)" }}
                    tickLine={false}
                    interval={calculateTickInterval(durationData.length)}
                  />
                  <YAxis
                    domain={[0, "auto"]}
                    tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                    axisLine={{ stroke: "var(--border-color)" }}
                    tickLine={false}
                    width={44}
                    label={{
                      value: "minutes",
                      angle: -90,
                      position: "insideLeft",
                      style: {
                        fill: "var(--text-muted)",
                        fontSize: 11,
                      },
                      offset: -4,
                    }}
                  />
                  <Tooltip content={<DurationTooltip />} />
                  <Legend
                    formatter={(value: string) =>
                      value.charAt(0).toUpperCase() + value.slice(1)
                    }
                    wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
                  />
                  <Bar
                    dataKey="deep"
                    stackId="duration"
                    fill={STAGE_COLORS.deep}
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="light"
                    stackId="duration"
                    fill={STAGE_COLORS.light}
                  />
                  <Bar
                    dataKey="rem"
                    stackId="duration"
                    fill={STAGE_COLORS.rem}
                  />
                  <Bar
                    dataKey="awake"
                    stackId="duration"
                    fill={STAGE_COLORS.wake}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div
                style={{
                  textAlign: "center",
                  padding: "40px 0",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                No duration data available.
              </div>
            )}
          </div>

          {/* Sleep Vitals Panel */}
          <div className="card">
            <div className="card-header">
              <Moon size={18} />
              <h3>Sleep Vitals</h3>
            </div>
            <p className="card-description">
              {selectedDate
                ? `Physiological data for the night of ${format(
                    parseISO(selectedDate),
                    "MMMM d, yyyy"
                  )}`
                : "Select a night to view vitals."}
            </p>

            {!selectedDate ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "32px 0",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                Select a night from the charts above to see vitals.
              </div>
            ) : vitalsLoading ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "32px 0",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                Loading vitals...
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: 16,
                }}
              >
                {/* SpO2 */}
                <div
                  style={{
                    background: "var(--bg-tertiary)",
                    borderRadius: "var(--radius-sm)",
                    padding: 20,
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      marginBottom: 12,
                      fontWeight: 600,
                    }}
                  >
                    SpO2
                  </div>
                  {spo2 ? (
                    <div>
                      <div
                        style={{
                          fontSize: 28,
                          fontWeight: 700,
                          color: "var(--text-primary)",
                          lineHeight: 1.2,
                        }}
                      >
                        {spo2.avg.toFixed(1)}
                        <span
                          style={{
                            fontSize: 14,
                            color: "var(--text-muted)",
                            fontWeight: 400,
                            marginLeft: 2,
                          }}
                        >
                          %
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: 12,
                          color: "var(--text-secondary)",
                          marginTop: 8,
                        }}
                      >
                        Min: {spo2.min.toFixed(1)}% | Max:{" "}
                        {spo2.max.toFixed(1)}%
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
                      No data
                    </div>
                  )}
                </div>

                {/* Breathing Rate */}
                <div
                  style={{
                    background: "var(--bg-tertiary)",
                    borderRadius: "var(--radius-sm)",
                    padding: 20,
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      marginBottom: 12,
                      fontWeight: 600,
                    }}
                  >
                    Breathing Rate
                  </div>
                  {breathingRate ? (
                    <div>
                      <div
                        style={{
                          fontSize: 28,
                          fontWeight: 700,
                          color: "var(--text-primary)",
                          lineHeight: 1.2,
                        }}
                      >
                        {breathingRate.breathingRate.toFixed(1)}
                        <span
                          style={{
                            fontSize: 14,
                            color: "var(--text-muted)",
                            fontWeight: 400,
                            marginLeft: 4,
                          }}
                        >
                          bpm
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
                      No data
                    </div>
                  )}
                </div>

                {/* Skin Temperature */}
                <div
                  style={{
                    background: "var(--bg-tertiary)",
                    borderRadius: "var(--radius-sm)",
                    padding: 20,
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      marginBottom: 12,
                      fontWeight: 600,
                    }}
                  >
                    Skin Temperature
                  </div>
                  {skinTemp ? (
                    <div>
                      <div
                        style={{
                          fontSize: 28,
                          fontWeight: 700,
                          color:
                            skinTemp.relativeTemp >= 0
                              ? "var(--success)"
                              : "var(--error)",
                          lineHeight: 1.2,
                        }}
                      >
                        {skinTemp.relativeTemp > 0 ? "+" : ""}
                        {skinTemp.relativeTemp.toFixed(2)}
                        <span
                          style={{
                            fontSize: 14,
                            color: "var(--text-muted)",
                            fontWeight: 400,
                            marginLeft: 2,
                          }}
                        >
                          {"\u00B0F"}
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: 12,
                          color: "var(--text-secondary)",
                          marginTop: 8,
                        }}
                      >
                        Relative to baseline
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
                      No data
                    </div>
                  )}
                </div>

                {/* Sleep Scores Summary */}
                {selectedLog && (
                  <div
                    style={{
                      background: "var(--bg-tertiary)",
                      borderRadius: "var(--radius-sm)",
                      padding: 20,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--text-muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        marginBottom: 12,
                        fontWeight: 600,
                      }}
                    >
                      Sleep Scores
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {selectedLog.overallScore != null && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 13,
                          }}
                        >
                          <span style={{ color: "var(--text-secondary)" }}>
                            Overall
                          </span>
                          <span
                            style={{
                              color: "var(--text-primary)",
                              fontWeight: 600,
                            }}
                          >
                            {selectedLog.overallScore}
                          </span>
                        </div>
                      )}
                      {selectedLog.compositionScore != null && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 13,
                          }}
                        >
                          <span style={{ color: "var(--text-secondary)" }}>
                            Composition
                          </span>
                          <span
                            style={{
                              color: "var(--text-primary)",
                              fontWeight: 600,
                            }}
                          >
                            {selectedLog.compositionScore}
                          </span>
                        </div>
                      )}
                      {selectedLog.revitalizationScore != null && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 13,
                          }}
                        >
                          <span style={{ color: "var(--text-secondary)" }}>
                            Revitalization
                          </span>
                          <span
                            style={{
                              color: "var(--text-primary)",
                              fontWeight: 600,
                            }}
                          >
                            {selectedLog.revitalizationScore}
                          </span>
                        </div>
                      )}
                      {selectedLog.durationScore != null && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 13,
                          }}
                        >
                          <span style={{ color: "var(--text-secondary)" }}>
                            Duration
                          </span>
                          <span
                            style={{
                              color: "var(--text-primary)",
                              fontWeight: 600,
                            }}
                          >
                            {selectedLog.durationScore}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Expanded Chart Modals */}
      <ChartModal
        isOpen={expandedChart === "score"}
        onClose={() => setExpandedChart(null)}
        title="Sleep Score Trend"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={scoreTrendData} onClick={handleScoreClick}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--border-color)"
              vertical={false}
            />
            <XAxis
              dataKey="dateLabel"
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--border-color)" }}
              tickLine={false}
              interval={calculateTickInterval(scoreTrendData.length)}
            />
            <YAxis
              domain={["dataMin - 5", "dataMax + 5"]}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--border-color)" }}
              tickLine={false}
              width={40}
            />
            <Tooltip content={<ScoreTooltip />} />
            <Line
              type="monotone"
              dataKey="score"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--accent)" }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartModal>

      <ChartModal
        isOpen={expandedChart === "duration"}
        onClose={() => setExpandedChart(null)}
        title="Sleep Duration Breakdown"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={durationData} onClick={handleDurationClick}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--border-color)"
              vertical={false}
            />
            <XAxis
              dataKey="dateLabel"
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--border-color)" }}
              tickLine={false}
              interval={calculateTickInterval(durationData.length)}
            />
            <YAxis
              domain={[0, "auto"]}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--border-color)" }}
              tickLine={false}
              width={50}
              label={{
                value: "minutes",
                angle: -90,
                position: "insideLeft",
                style: { fill: "var(--text-muted)", fontSize: 12 },
              }}
            />
            <Tooltip content={<DurationTooltip />} />
            <Legend
              formatter={(value: string) =>
                value.charAt(0).toUpperCase() + value.slice(1)
              }
            />
            <Bar dataKey="deep" stackId="duration" fill={STAGE_COLORS.deep} />
            <Bar dataKey="light" stackId="duration" fill={STAGE_COLORS.light} />
            <Bar dataKey="rem" stackId="duration" fill={STAGE_COLORS.rem} />
            <Bar
              dataKey="awake"
              stackId="duration"
              fill={STAGE_COLORS.wake}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </ChartModal>
    </div>
  );
}
