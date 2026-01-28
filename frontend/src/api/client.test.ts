import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getAuthUrl } from "./client";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("API Client", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("getAuthUrl", () => {
    it("returns the Fitbit auth URL", () => {
      const url = getAuthUrl();
      expect(url).toBe("http://localhost:8000/api/auth/fitbit");
    });
  });

  describe("request helper (via getOverview)", () => {
    it("fetches data and returns JSON on success", async () => {
      const mockData = {
        date: "2024-06-15",
        heartRate: { resting_heart_rate: 62 },
        sleep: null,
        activity: null,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockData),
      });

      const { getOverview } = await import("./client");
      const result = await getOverview("2024-06-15");
      expect(result).toEqual(mockData);
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/data/overview?date=2024-06-15",
        expect.objectContaining({
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        })
      );
    });

    it("throws ApiError on non-ok response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        text: () => Promise.resolve("Not Found"),
      });

      const { getOverview } = await import("./client");
      await expect(getOverview("2024-06-15")).rejects.toThrow("Not Found");
    });

    it("includes status code in error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server Error"),
      });

      const { getOverview } = await import("./client");
      try {
        await getOverview("2024-06-15");
        expect.fail("Should have thrown");
      } catch (err: unknown) {
        expect((err as { status: number }).status).toBe(500);
      }
    });
  });

  describe("getHeartRateIntraday", () => {
    it("calls the correct endpoint", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ date: "2024-06-15", data: [] }),
      });

      const { getHeartRateIntraday } = await import("./client");
      await getHeartRateIntraday("2024-06-15");
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/data/heart-rate/intraday?date=2024-06-15",
        expect.any(Object)
      );
    });
  });

  describe("getCorrelation", () => {
    it("passes all query parameters", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            xMetric: "resting_hr",
            yMetric: "steps",
            correlation: 0.5,
            points: [],
            availableMetrics: [],
          }),
      });

      const { getCorrelation } = await import("./client");
      await getCorrelation("resting_hr", "steps", "2024-01-01", "2024-06-30");
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/data/correlations?x=resting_hr&y=steps&start=2024-01-01&end=2024-06-30",
        expect.any(Object)
      );
    });
  });

  describe("triggerSync", () => {
    it("sends a POST request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ status: "success", message: "Synced" }),
      });

      const { triggerSync } = await import("./client");
      await triggerSync();
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/sync",
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});
