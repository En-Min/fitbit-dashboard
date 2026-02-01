import { useState, useCallback, useEffect } from "react";
import { format, subDays, subMonths, subYears } from "date-fns";
import { Calendar } from "lucide-react";

const API_BASE = "http://localhost:8000";

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onChange: (start: string, end: string) => void;
}

interface Preset {
  label: string;
  days?: number;
  months?: number;
  years?: number;
  allTime?: boolean;
}

const PRESETS: Preset[] = [
  { label: "Today", days: 0 },
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "1y", years: 1 },
  { label: "All", allTime: true },
];

export default function DateRangePicker({
  startDate,
  endDate,
  onChange,
}: DateRangePickerProps) {
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [earliestDate, setEarliestDate] = useState<string | null>(null);

  const today = format(new Date(), "yyyy-MM-dd");

  // Fetch earliest date from API on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/metrics`)
      .then((res) => res.json())
      .then((data) => {
        const dates: string[] = [];
        if (data.metrics && Array.isArray(data.metrics)) {
          for (const metric of data.metrics) {
            if (metric.startDate) dates.push(metric.startDate);
          }
        }
        if (dates.length > 0) {
          dates.sort();
          setEarliestDate(dates[0]);
        }
      })
      .catch(() => {
        // Fallback to 5 years ago if fetch fails
        setEarliestDate(format(subYears(new Date(), 5), "yyyy-MM-dd"));
      });
  }, []);

  const applyPreset = useCallback(
    (preset: Preset) => {
      const end = new Date();
      let start: Date;

      if (preset.allTime && earliestDate) {
        setActivePreset(preset.label);
        onChange(earliestDate, format(end, "yyyy-MM-dd"));
        return;
      } else if (preset.years) {
        start = subYears(end, preset.years);
      } else if (preset.months) {
        start = subMonths(end, preset.months);
      } else {
        start = subDays(end, preset.days ?? 0);
      }

      setActivePreset(preset.label);
      onChange(format(start, "yyyy-MM-dd"), format(end, "yyyy-MM-dd"));
    },
    [onChange, earliestDate]
  );

  const handleStartChange = (value: string) => {
    setActivePreset(null);
    onChange(value, endDate);
  };

  const handleEndChange = (value: string) => {
    setActivePreset(null);
    onChange(startDate, value);
  };

  return (
    <div className="date-range-picker">
      <div className="date-range-presets">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            className={`preset-btn ${activePreset === preset.label ? "active" : ""}`}
            onClick={() => applyPreset(preset)}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="date-range-inputs">
        <div className="date-input-group">
          <Calendar size={14} />
          <input
            type="date"
            value={startDate}
            max={endDate || today}
            onChange={(e) => handleStartChange(e.target.value)}
          />
        </div>
        <span className="date-range-separator">to</span>
        <div className="date-input-group">
          <Calendar size={14} />
          <input
            type="date"
            value={endDate}
            min={startDate}
            max={today}
            onChange={(e) => handleEndChange(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
