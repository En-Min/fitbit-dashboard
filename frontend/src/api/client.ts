import type {
  OverviewData,
  HeartRateReading,
  HeartRateDaily,
  SleepLog,
  SleepStage,
  SpO2Reading,
  HRVDaily,
  BreathingRate,
  SkinTemperature,
  VO2Max,
  ActivityDaily,
  StressScore,
  Exercise,
  MetricInfo,
} from "../types";

const BASE_URL = "http://localhost:8000/api";

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(
      body || `Request failed: ${response.statusText}`,
      response.status
    );
  }

  return response.json() as Promise<T>;
}

// --- Overview ---

export async function getOverview(date: string): Promise<OverviewData> {
  return request<OverviewData>(`/data/overview?date=${date}`);
}

// --- Heart Rate ---

export async function getHeartRateIntraday(
  date: string
): Promise<{ date: string; data: HeartRateReading[] }> {
  return request(`/data/heart-rate/intraday?date=${date}`);
}

export async function getHeartRateDaily(
  start: string,
  end: string
): Promise<{ data: HeartRateDaily[] }> {
  return request(`/data/heart-rate/daily?start=${start}&end=${end}`);
}

// --- Sleep ---

export async function getSleepLogs(
  start: string,
  end: string
): Promise<{ data: SleepLog[] }> {
  return request(`/data/sleep?start=${start}&end=${end}`);
}

export async function getSleepStages(
  sleepLogId: number
): Promise<{ data: SleepStage[] }> {
  return request(`/data/sleep/stages/${sleepLogId}`);
}

// --- SpO2 ---

export async function getSpO2(
  start: string,
  end: string
): Promise<{ data: SpO2Reading[] }> {
  return request(`/data/spo2?start=${start}&end=${end}`);
}

export async function getSpO2Intraday(
  date: string
): Promise<{ data: Array<{ timestamp: string; spo2: number }> }> {
  return request(`/data/spo2/intraday?date=${date}`);
}

// --- HRV ---

export async function getHRV(
  start: string,
  end: string
): Promise<{ data: HRVDaily[] }> {
  return request(`/data/hrv?start=${start}&end=${end}`);
}

export async function getHRVIntraday(
  date: string
): Promise<{ data: Array<{ timestamp: string; rmssd: number; hf: number; lf: number }> }> {
  return request(`/data/hrv/intraday?date=${date}`);
}

// --- Breathing Rate ---

export async function getBreathingRate(
  start: string,
  end: string
): Promise<{ data: BreathingRate[] }> {
  return request(`/data/breathing-rate?start=${start}&end=${end}`);
}

// --- Skin Temperature ---

export async function getSkinTemperature(
  start: string,
  end: string
): Promise<{ data: SkinTemperature[] }> {
  return request(`/data/skin-temperature?start=${start}&end=${end}`);
}

// --- VO2 Max ---

export async function getVO2Max(
  start: string,
  end: string
): Promise<{ data: VO2Max[] }> {
  return request(`/data/vo2-max?start=${start}&end=${end}`);
}

// --- Activity ---

export async function getActivityDaily(
  start: string,
  end: string
): Promise<{ data: ActivityDaily[] }> {
  return request(`/data/activity?start=${start}&end=${end}`);
}

export async function getActivityIntraday(
  date: string,
  metric: string
): Promise<{ data: Array<{ timestamp: string; value: number }> }> {
  return request(`/data/activity/intraday?date=${date}&metric=${metric}`);
}

// --- Stress ---

export async function getStressScores(
  start: string,
  end: string
): Promise<{ data: StressScore[] }> {
  return request(`/data/stress?start=${start}&end=${end}`);
}

// --- Readiness ---

export async function getReadinessScores(
  start: string,
  end: string
): Promise<{ data: Array<{ date: string; readinessScore: number }> }> {
  return request(`/data/readiness?start=${start}&end=${end}`);
}

// --- Exercises ---

export async function getExercises(
  start: string,
  end: string
): Promise<{ data: Exercise[] }> {
  return request(`/data/exercises?start=${start}&end=${end}`);
}

// --- Metrics ---

export async function getMetrics(): Promise<{ metrics: MetricInfo[] }> {
  return request("/metrics");
}

// --- Correlations ---

export interface CorrelationResult {
  xMetric: string;
  yMetric: string;
  correlation: number | null;
  points: Array<{ date: string; x: number; y: number }>;
  availableMetrics: string[];
}

export async function getCorrelation(
  x: string,
  y: string,
  start: string,
  end: string
): Promise<CorrelationResult> {
  return request<CorrelationResult>(
    `/data/correlations?x=${x}&y=${y}&start=${start}&end=${end}`
  );
}

// --- Upload ---

export interface UploadResult {
  status: string;
  summary: Record<string, number>;
}

export async function uploadExport(
  file: File,
  onProgress?: (pct: number) => void
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_URL}/upload`);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new ApiError(xhr.responseText || "Upload failed", xhr.status));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new ApiError("Network error during upload", 0));
    });

    const formData = new FormData();
    formData.append("file", file);
    xhr.send(formData);
  });
}

// --- Auth ---

export interface AuthStatus {
  authenticated: boolean;
  user_id?: string;
  expires_at?: number;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>("/auth/status");
}

export function getAuthUrl(): string {
  return `${BASE_URL}/auth/fitbit`;
}

// --- Sync ---

export interface SyncResult {
  status: string;
  message: string;
}

export async function triggerSync(): Promise<SyncResult> {
  return request<SyncResult>("/sync", { method: "POST" });
}
