import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import FirstTimerTour from "../../components/FirstTimerTour";

const STORAGE_KEY = "climatefacts_tour_completed_v1";

describe("FirstTimerTour — first-timer walkthrough", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders the modal automatically when no completion flag", async () => {
    render(<FirstTimerTour />);
    await waitFor(() =>
      expect(screen.getByTestId("first-timer-tour-modal")).toBeInTheDocument()
    );
    expect(screen.getByText(/Welcome to Climatefacts\.ai/i)).toBeInTheDocument();
  });

  it("does NOT auto-open when localStorage flag is set", async () => {
    localStorage.setItem(STORAGE_KEY, "true");
    render(<FirstTimerTour />);
    // Wait one tick for hydration effect
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.queryByTestId("first-timer-tour-modal")).not.toBeInTheDocument();
  });

  it("Next button advances steps", async () => {
    render(<FirstTimerTour />);
    await waitFor(() =>
      expect(screen.getByTestId("first-timer-tour-modal")).toBeInTheDocument()
    );
    // Step 1: Welcome
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
    expect(screen.getByText(/Explore the world map/i)).toBeInTheDocument();
  });

  it("Skip button closes the modal and marks completed", async () => {
    render(<FirstTimerTour />);
    await waitFor(() =>
      expect(screen.getByTestId("first-timer-tour-modal")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /Skip tour/i }));
    await waitFor(() =>
      expect(screen.queryByTestId("first-timer-tour-modal")).not.toBeInTheDocument()
    );
    expect(localStorage.getItem(STORAGE_KEY)).toBe("true");
  });

  it("Finish button on last step closes + marks completed", async () => {
    render(<FirstTimerTour />);
    await waitFor(() =>
      expect(screen.getByTestId("first-timer-tour-modal")).toBeInTheDocument()
    );
    // Advance through steps to the last one
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    expect(screen.getByText("Step 4 of 4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Finish/i }));
    await waitFor(() =>
      expect(screen.queryByTestId("first-timer-tour-modal")).not.toBeInTheDocument()
    );
    expect(localStorage.getItem(STORAGE_KEY)).toBe("true");
  });

  it("Quick tour button re-opens after completion", async () => {
    localStorage.setItem(STORAGE_KEY, "true");
    render(<FirstTimerTour />);
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.queryByTestId("first-timer-tour-modal")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("first-timer-tour-button"));
    expect(screen.getByTestId("first-timer-tour-modal")).toBeInTheDocument();
    // Re-opened at step 1
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
  });

  it("X (close) button closes the modal AND records completion", async () => {
    render(<FirstTimerTour />);
    await waitFor(() =>
      expect(screen.getByTestId("first-timer-tour-modal")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /Close tour/i }));
    await waitFor(() =>
      expect(screen.queryByTestId("first-timer-tour-modal")).not.toBeInTheDocument()
    );
    expect(localStorage.getItem(STORAGE_KEY)).toBe("true");
  });
});
