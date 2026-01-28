export interface HeartRateReading {
  timestamp: string;
  bpm: number;
  confidence?: number;
}

export interface HeartRateDaily {
  date: string;
  restingHeartRate: number;
  fatBurnMinutes: number;
  cardioMinutes: number;
  peakMinutes: number;
}

export interface SleepLog {
  id: number;
  date: string;
  startTime: string;
  endTime: string;
  durationMs: number;
  efficiency: number;
  minutesAsleep: number;
  minutesAwake: number;
  overallScore?: number;
  compositionScore?: number;
  revitalizationScore?: number;
  durationScore?: number;
  deepSleepMinutes?: number;
  remSleepMinutes?: number;
  lightSleepMinutes?: number;
}

export interface SleepStage {
  timestamp: string;
  stage: string;
  durationSeconds: number;
}

export interface SpO2Reading {
  timestamp: string;
  spo2: number;
}

export interface HRVReading {
  timestamp: string;
  rmssd: number;
}

export interface HRVDaily {
  date: string;
  dailyRmssd: number;
  deepRmssd?: number;
}

export interface BreathingRate {
  date: string;
  breathingRate: number;
}

export interface SkinTemperature {
  date: string;
  relativeTemp: number;
}

export interface VO2Max {
  date: string;
  vo2Max: number;
}

export interface ActivityDaily {
  date: string;
  steps: number;
  distanceKm: number;
  caloriesTotal: number;
  caloriesActive: number;
  minutesSedentary: number;
  minutesLightlyActive: number;
  minutesFairlyActive: number;
  minutesVeryActive: number;
  activeZoneMinutes: number;
}

export interface ActivityIntraday {
  timestamp: string;
  metric: string;
  value: number;
}

export interface StressScore {
  date: string;
  stressScore: number;
}

export interface Exercise {
  id: number;
  date: string;
  startTime: string;
  activityName: string;
  durationMs: number;
  calories: number;
  averageHeartRate?: number;
}

export interface MetricInfo {
  name: string;
  label: string;
  unit: string;
  startDate?: string;
  endDate?: string;
}

export interface OverviewData {
  date: string;
  heartRate?: HeartRateDaily;
  sleep?: SleepLog;
  activity?: ActivityDaily;
  spo2?: { avg: number };
  hrv?: HRVDaily;
  breathingRate?: BreathingRate;
  skinTemp?: SkinTemperature;
  vo2Max?: VO2Max;
  stress?: StressScore;
}
