import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import WeatherContext from "@/components/WeatherContext";

// Deferred #21 (2026-05-25) — WeatherContext now distinguishes
// loading / ready / empty / auth (401) / tier (403) / error states.
// Previously it silently hid on ANY non-200, so anonymous users had
// no signal that weather context existed but required sign-in.

const mockGetWeather = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getArticleWeatherContext: (...args: any[]) => mockGetWeather(...args),
  },
}));

describe("WeatherContext (state-aware)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders weather grid when API returns data", async () => {
    mockGetWeather.mockResolvedValue({
      locations_found: 1,
      weather_contexts: [
        {
          location_name: "Berlin",
          coordinates: { lat: 52.52, lon: 13.41 },
          current_weather: { temperature_c: 18, weather_code: 1 },
          anomaly: null,
          historical_normals: null,
        },
      ],
    });
    render(<WeatherContext articleId="a-1" />);
    await waitFor(() => {
      expect(screen.getByText(/Local Weather Context/i)).toBeInTheDocument();
    });
    expect(screen.getByText("Berlin")).toBeInTheDocument();
  });

  it("shows 'sign in' affordance on 401", async () => {
    mockGetWeather.mockRejectedValue({ response: { status: 401 } });
    render(<WeatherContext articleId="a-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-auth-required")).toBeInTheDocument();
    });
    expect(screen.getByText(/Sign in/i)).toBeInTheDocument();
  });

  it("shows 'upgrade to Standard' affordance on 403", async () => {
    mockGetWeather.mockRejectedValue({ response: { status: 403 } });
    render(<WeatherContext articleId="a-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-tier-required")).toBeInTheDocument();
    });
    expect(screen.getByText(/Standard or higher/i)).toBeInTheDocument();
  });

  it("shows empty state when no locations detected (404 or empty array)", async () => {
    mockGetWeather.mockResolvedValue({
      locations_found: 0,
      weather_contexts: [],
    });
    render(<WeatherContext articleId="a-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-empty")).toBeInTheDocument();
    });
    expect(screen.getByText(/No geographic locations detected/i)).toBeInTheDocument();
  });

  it("shows error state on 5xx", async () => {
    mockGetWeather.mockRejectedValue({ response: { status: 503 } });
    render(<WeatherContext articleId="a-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-error")).toBeInTheDocument();
    });
    expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
  });

  it("treats 404 as empty (no data, not error)", async () => {
    mockGetWeather.mockRejectedValue({ response: { status: 404 } });
    render(<WeatherContext articleId="a-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-empty")).toBeInTheDocument();
    });
  });
});
