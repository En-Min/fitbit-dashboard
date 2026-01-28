import { useState, useEffect, useCallback, useMemo } from "react";
import { format, subDays } from "date-fns";
import { Activity as ActivityIcon, Loader } from "lucide-react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";
import DateRangePicker from "../components/DateRangePicker";
import type {
  ActivityDaily,
  VO2Max,
  Exercise,
} from "../types";

const API_BASE = "http://localhost:8000";

interface IntradayPoint {
  timestamp: string;
  value: number;
}

interface HeatmapCell {
  day: number; // 0=Mon, 6=Sun
  hour: number; // 0-23
  value: number;
}

const DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function formatDuration(ms: number): string {
  const totalMinutes = Math.round(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

function getHeatmapColor(value: number, maxValue: number): string {
  if (value === 0 || maxValue === 0) return "var(--bg-tertiary)";
  const intensity = value / maxValue;
  if (intensity < 0.2) return "#1a3a2a";
  if (intensity < 0.4) return "#1e5631";
  if (intensity < 0.6) return "#2d8a4e";
  if (intensity < 0.8) return "#34d399";
  return "#6ee7b7";
}

export default function Activity() {
  const today = format(new Date(), "yyyy-MM-dd");
  const thirtyDaysAgo = format(subDays(new Date(), 30), "yyyy-MM-dd");

  const [startDate, setStartDate] = useState(thirtyDaysAgo);
  const [endDate, setEndDate] = useState(today);

  const [activityData, setActivityData] = useState<ActivityDaily[]>([]);
  const [vo2Data, setVo2Data] = useState<VO2Max[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [intradayData, setIntradayData] = useState<IntradayPoint[]>([]);
  const [heatmapDate, setHeatmapDate] = useState(today);

  const [loadingActivity, setLoadingActivity] = useState(false);
  const [loadingVo2, setLoadingVo2] = useState(false);
  const [loadingExercises, setLoadingExercises] = useState(false);
  const [loadingIntraday, setLoadingIntraday] = useState(false);

  const [errorActivity, setErrorActivity] = useState("");
  const [errorVo2, setErrorVo2] = useState("");
  const [errorExercises, setErrorExercises] = useState("");
  const [errorIntraday, setErrorIntraday] = useState("");

  const handleDateChange = useCallback((start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
  }, []);

  // Fetch activity daily data
  useEffect(() => {
    const controller = new AbortController();
    setLoadingActivity(true);
    setErrorActivity("");

    fetch(
      `${API_BASE}/api/data/activity?start=${startDate}&end=${endDate}`,
      { signal: controller.signal }
    )
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => setActivityData(json.data ?? []))
      .catch((err) => {
        if (err.name !== "AbortError") setErrorActivity(err.message);
      })
      .finally(() => setLoadingActivity(false));

    return () => controller.abort();
  }, [startDate, endDate]);

  // Fetch VO2 max data
  useEffect(() => {
    const controller = new AbortController();
    setLoadingVo2(true);
    setErrorVo2("");

    fetch(
      `${API_BASE}/api/data/vo2-max?start=${startDate}&end=${endDate}`,
      { signal: controller.signal }
    )
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => setVo2Data(json.data ?? []))
      .catch((err) => {
        if (err.name !== "AbortError") setErrorVo2(err.message);
      })
      .finally(() => setLoadingVo2(false));

    return () => controller.abort();
  }, [startDate, endDate]);

  // Fetch exercises
  useEffect(() => {
    const controller = new AbortController();
    setLoadingExercises(true);
    setErrorExercises("");

    fetch(
      `${API_BASE}/api/data/exercises?start=${startDate}&end=${endDate}`,
      { signal: controller.signal }
    )
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => setExercises(json.data ?? []))
      .catch((err) => {
        if (err.name !== "AbortError") setErrorExercises(err.message);
      })
      .finally(() => setLoadingExercises(false));

    return () => controller.abort();
  }, [startDate, endDate]);

  // Fetch intraday steps for heatmap
  useEffect(() => {
    const controller = new AbortController();
    setLoadingIntraday(true);
    setErrorIntraday("");

    // Fetch 7 days ending on heatmapDate
    const dates: string[] = [];
    for (let i = 6; i >= 0; i--) {
      dates.push(format(subDays(new Date(heatmapDate + "T12:00:00"), i), "yyyy-MM-dd"));
    }

    Promise.all(
      dates.map((d) =>
        fetch(
          `${API_BASE}/api/data/activity/intraday?date=${d}&metric=steps`,
          { signal: controller.signal }
        )
          .then((res) => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
          })
          .then((json) => ({ date: d, points: (json.data ?? []) as IntradayPoint[] }))
      )
    )
      .then((results) => {
        // Flatten all points for use in heatmap
        const all: IntradayPoint[] = [];
        results.forEach((r) => all.push(...r.points));
        setIntradayData(all);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setErrorIntraday(err.message);
      })
      .finally(() => setLoadingIntraday(false));

    return () => controller.abort();
  }, [heatmapDate]);

  // Build heatmap cells from intraday data
  const heatmapCells = useMemo((): { cells: HeatmapCell[]; maxValue: number } => {
    const buckets: Record<string, number> = {};

    intradayData.forEach((point) => {
      const dt = new Date(point.timestamp);
      // getDay: 0=Sun, 1=Mon... convert to 0=Mon, 6=Sun
      const rawDay = dt.getDay();
      const day = rawDay === 0 ? 6 : rawDay - 1;
      const hour = dt.getHours();
      const key = `${day}-${hour}`;
      buckets[key] = (buckets[key] || 0) + point.value;
    });

    let maxValue = 0;
    const cells: HeatmapCell[] = [];

    for (let day = 0; day < 7; day++) {
      for (let hour = 0; hour < 24; hour++) {
        const value = buckets[`${day}-${hour}`] || 0;
        if (value > maxValue) maxValue = value;
        cells.push({ day, hour, value });
      }
    }

    return { cells, maxValue };
  }, [intradayData]);

  // Chart data preparations
  const stepsChartData = useMemo(
    () =>
      activityData.map((d) => ({
        date: format(new Date(d.date + "T12:00:00"), "MMM d"),
        steps: d.steps,
        rawDate: d.date,
      })),
    [activityData]
  );

  const activityMinutesData = useMemo(
    () =>
      activityData.map((d) => ({
        date: format(new Date(d.date + "T12:00:00"), "MMM d"),
        Sedentary: d.minutesSedentary,
        "Lightly Active": d.minutesLightlyActive,
        "Fairly Active": d.minutesFairlyActive,
        "Very Active": d.minutesVeryActive,
      })),
    [activityData]
  );

  const vo2ChartData = useMemo(
    () =>
      vo2Data.map((d) => ({
        date: format(new Date(d.date + "T12:00:00"), "MMM d"),
        vo2Max: d.vo2Max,
      })),
    [vo2Data]
  );

  const chartTickFormatter = useCallback(
    (value: number) => value.toLocaleString(),
    []
  );

  // Heatmap week label
  const heatmapWeekLabel = useMemo(() => {
    const end = new Date(heatmapDate + "T12:00:00");
    const start = subDays(end, 6);
    return `${format(start, "MMM d")} - ${format(end, "MMM d, yyyy")}`;
  }, [heatmapDate]);

  return (
    <div className="page">
      <div className="page-header">
        <ActivityIcon size={24} />
        <h2>Activity &amp; Fitness</h2>
      </div>

      <DateRangePicker
        startDate={startDate}
        endDate={endDate}
        onChange={handleDateChange}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* ===== Steps Trend ===== */}
        <div className="card">
          <div className="card-header">
            <h3>Steps Trend</h3>
          </div>
          <p className="card-description">
            Daily step count with a 10,000-step goal reference line.
          </p>
          {loadingActivity ? (
            <LoadingIndicator />
          ) : errorActivity ? (
            <ErrorMessage message={errorActivity} />
          ) : activityData.length === 0 ? (
            <EmptyState message="No activity data available for this date range." />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart
                data={stepsChartData}
                margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border-color)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border-color)" }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={chartTickFormatter}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    fontSize: 13,
                  }}
                  formatter={(value: number | string) => [
                    Number(value).toLocaleString(),
                    "Steps",
                  ]}
                  cursor={{ fill: "rgba(255,255,255,0.04)" }}
                />
                <ReferenceLine
                  y={10000}
                  stroke="var(--accent)"
                  strokeDasharray="6 4"
                  strokeWidth={1.5}
                  label={{
                    value: "10k goal",
                    position: "insideTopRight",
                    fill: "var(--accent)",
                    fontSize: 12,
                  }}
                />
                <Bar
                  dataKey="steps"
                  fill="var(--accent)"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={28}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ===== Activity Heatmap ===== */}
        <div className="card">
          <div className="card-header">
            <h3>Activity Heatmap</h3>
          </div>
          <p className="card-description">
            Hourly step intensity across the week. Darker cells indicate more
            steps. Select a week-ending date to explore patterns.
          </p>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 16,
            }}
          >
            <label
              style={{
                fontSize: 13,
                color: "var(--text-secondary)",
                fontWeight: 500,
              }}
            >
              Week ending:
            </label>
            <div className="date-input-group">
              <input
                type="date"
                value={heatmapDate}
                max={today}
                onChange={(e) => setHeatmapDate(e.target.value)}
              />
            </div>
            <span
              style={{
                fontSize: 13,
                color: "var(--text-muted)",
              }}
            >
              {heatmapWeekLabel}
            </span>
          </div>
          {loadingIntraday ? (
            <LoadingIndicator />
          ) : errorIntraday ? (
            <ErrorMessage message={errorIntraday} />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "56px repeat(7, 1fr)",
                  gridTemplateRows: `auto repeat(24, 1fr)`,
                  gap: 2,
                  minWidth: 480,
                }}
              >
                {/* Column headers: days */}
                <div /> {/* empty corner cell */}
                {DAYS_OF_WEEK.map((day) => (
                  <div
                    key={day}
                    style={{
                      textAlign: "center",
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--text-secondary)",
                      padding: "4px 0",
                    }}
                  >
                    {day}
                  </div>
                ))}
                {/* Rows: hours */}
                {HOURS.map((hour) => (
                  <>
                    <div
                      key={`label-${hour}`}
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                        paddingRight: 8,
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {hour.toString().padStart(2, "0")}:00
                    </div>
                    {DAYS_OF_WEEK.map((_, dayIdx) => {
                      const cell = heatmapCells.cells.find(
                        (c) => c.day === dayIdx && c.hour === hour
                      );
                      const value = cell?.value ?? 0;
                      return (
                        <div
                          key={`${dayIdx}-${hour}`}
                          title={`${DAYS_OF_WEEK[dayIdx]} ${hour.toString().padStart(2, "0")}:00 - ${value.toLocaleString()} steps`}
                          style={{
                            backgroundColor: getHeatmapColor(
                              value,
                              heatmapCells.maxValue
                            ),
                            borderRadius: 3,
                            minHeight: 18,
                            cursor: "default",
                            transition: "background-color 0.15s ease",
                          }}
                        />
                      );
                    })}
                  </>
                ))}
              </div>
              {/* Legend */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginTop: 12,
                  justifyContent: "flex-end",
                }}
              >
                <span
                  style={{ fontSize: 11, color: "var(--text-muted)" }}
                >
                  Less
                </span>
                {[0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => (
                  <div
                    key={t}
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: 3,
                      backgroundColor:
                        t === 0
                          ? "var(--bg-tertiary)"
                          : getHeatmapColor(t, 1),
                    }}
                  />
                ))}
                <span
                  style={{ fontSize: 11, color: "var(--text-muted)" }}
                >
                  More
                </span>
              </div>
            </div>
          )}
        </div>

        {/* ===== Activity Minutes Breakdown ===== */}
        <div className="card">
          <div className="card-header">
            <h3>Activity Minutes Breakdown</h3>
          </div>
          <p className="card-description">
            Daily breakdown of sedentary, lightly active, fairly active, and
            very active minutes.
          </p>
          {loadingActivity ? (
            <LoadingIndicator />
          ) : errorActivity ? (
            <ErrorMessage message={errorActivity} />
          ) : activityData.length === 0 ? (
            <EmptyState message="No activity data available for this date range." />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart
                data={activityMinutesData}
                margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border-color)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border-color)" }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  label={{
                    value: "minutes",
                    angle: -90,
                    position: "insideLeft",
                    fill: "var(--text-muted)",
                    fontSize: 12,
                    offset: 0,
                  }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    fontSize: 13,
                  }}
                  formatter={(value: number | string, name: string) => [
                    `${value} min`,
                    name,
                  ]}
                  cursor={{ fill: "rgba(255,255,255,0.04)" }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
                />
                <Bar
                  dataKey="Sedentary"
                  stackId="minutes"
                  fill="#455A64"
                  radius={[0, 0, 0, 0]}
                  maxBarSize={28}
                />
                <Bar
                  dataKey="Lightly Active"
                  stackId="minutes"
                  fill="#78909C"
                  radius={[0, 0, 0, 0]}
                  maxBarSize={28}
                />
                <Bar
                  dataKey="Fairly Active"
                  stackId="minutes"
                  fill="#FF9800"
                  radius={[0, 0, 0, 0]}
                  maxBarSize={28}
                />
                <Bar
                  dataKey="Very Active"
                  stackId="minutes"
                  fill="#F44336"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={28}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ===== VO2 Max Trend ===== */}
        <div className="card">
          <div className="card-header">
            <h3>VO2 Max Trend</h3>
          </div>
          <p className="card-description">
            Estimated cardiorespiratory fitness (VO2 Max) over time.
          </p>
          {loadingVo2 ? (
            <LoadingIndicator />
          ) : errorVo2 ? (
            <ErrorMessage message={errorVo2} />
          ) : vo2Data.length === 0 ? (
            <EmptyState message="No VO2 Max data available for this date range." />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart
                data={vo2ChartData}
                margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border-color)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border-color)" }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  domain={["dataMin - 2", "dataMax + 2"]}
                  label={{
                    value: "mL/kg/min",
                    angle: -90,
                    position: "insideLeft",
                    fill: "var(--text-muted)",
                    fontSize: 12,
                    offset: 0,
                  }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    fontSize: 13,
                  }}
                  formatter={(value: number | string) => [
                    `${Number(value).toFixed(1)} mL/kg/min`,
                    "VO2 Max",
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="vo2Max"
                  stroke="var(--success)"
                  strokeWidth={2}
                  dot={{ fill: "var(--success)", r: 3, strokeWidth: 0 }}
                  activeDot={{ r: 5, strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ===== Exercise Log ===== */}
        <div className="card">
          <div className="card-header">
            <h3>Exercise Log</h3>
          </div>
          <p className="card-description">
            Logged exercise sessions during the selected period.
          </p>
          {loadingExercises ? (
            <LoadingIndicator />
          ) : errorExercises ? (
            <ErrorMessage message={errorExercises} />
          ) : exercises.length === 0 ? (
            <EmptyState message="No exercises logged for this date range." />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: 13,
                }}
              >
                <thead>
                  <tr>
                    {["Activity", "Date", "Start", "Duration", "Calories", "Avg HR"].map(
                      (header) => (
                        <th
                          key={header}
                          style={{
                            textAlign: "left",
                            padding: "10px 12px",
                            borderBottom: "1px solid var(--border-color)",
                            color: "var(--text-muted)",
                            fontWeight: 600,
                            fontSize: 12,
                            textTransform: "uppercase",
                            letterSpacing: "0.04em",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {header}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {exercises.map((ex) => (
                    <tr
                      key={ex.id}
                      style={{
                        borderBottom: "1px solid var(--border-color)",
                      }}
                    >
                      <td
                        style={{
                          padding: "10px 12px",
                          fontWeight: 500,
                          color: "var(--text-primary)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ex.activityName}
                      </td>
                      <td
                        style={{
                          padding: "10px 12px",
                          color: "var(--text-secondary)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {format(new Date(ex.date + "T12:00:00"), "MMM d, yyyy")}
                      </td>
                      <td
                        style={{
                          padding: "10px 12px",
                          color: "var(--text-secondary)",
                          fontVariantNumeric: "tabular-nums",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ex.startTime
                          ? format(new Date(ex.startTime), "h:mm a")
                          : "--"}
                      </td>
                      <td
                        style={{
                          padding: "10px 12px",
                          color: "var(--text-secondary)",
                          fontVariantNumeric: "tabular-nums",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {formatDuration(ex.durationMs)}
                      </td>
                      <td
                        style={{
                          padding: "10px 12px",
                          color: "var(--warning)",
                          fontVariantNumeric: "tabular-nums",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ex.calories.toLocaleString()} kcal
                      </td>
                      <td
                        style={{
                          padding: "10px 12px",
                          color: ex.averageHeartRate
                            ? "var(--error)"
                            : "var(--text-muted)",
                          fontVariantNumeric: "tabular-nums",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ex.averageHeartRate
                          ? `${ex.averageHeartRate} bpm`
                          : "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ===== Small helper components ===== */

function LoadingIndicator() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 48,
        color: "var(--text-muted)",
        gap: 8,
        fontSize: 14,
      }}
    >
      <Loader size={18} className="spin" />
      Loading...
    </div>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="status-message error">
      Failed to load data: {message}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "40px 20px",
        color: "var(--text-muted)",
        fontSize: 14,
      }}
    >
      {message}
    </div>
  );
}
