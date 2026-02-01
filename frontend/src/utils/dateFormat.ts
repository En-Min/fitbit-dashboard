import { format, parseISO } from "date-fns";

/**
 * Determines if a date range spans multiple years
 */
export function spansMultipleYears(dates: string[]): boolean {
  if (dates.length < 2) return false;
  const years = new Set(dates.map((d) => new Date(d).getFullYear()));
  return years.size > 1;
}

/**
 * Smart date formatter that includes year when data spans multiple years
 */
export function formatDateLabel(
  dateStr: string,
  includeYear: boolean
): string {
  try {
    const date = parseISO(dateStr);
    if (includeYear) {
      return format(date, "MMM d ''yy"); // Jan 5 '22
    }
    return format(date, "MMM d"); // Jan 5
  } catch {
    return dateStr;
  }
}

/**
 * Creates a tick formatter function for X-axis based on data range
 */
export function createDateTickFormatter(dates: string[]): (date: string) => string {
  const needsYear = spansMultipleYears(dates);
  return (dateStr: string) => formatDateLabel(dateStr, needsYear);
}

/**
 * Calculate smart interval for X-axis ticks based on data length
 * Returns interval that shows roughly 8-12 ticks
 */
export function calculateTickInterval(dataLength: number): number | "preserveStartEnd" {
  if (dataLength <= 12) return 0;
  if (dataLength <= 30) return Math.floor(dataLength / 10);
  if (dataLength <= 90) return Math.floor(dataLength / 10);
  if (dataLength <= 365) return Math.floor(dataLength / 12);
  return Math.floor(dataLength / 12);
}
