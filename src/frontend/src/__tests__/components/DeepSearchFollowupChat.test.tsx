import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DeepSearchFollowupChat from "@/components/DeepSearchFollowupChat";

// Slice 6 (2026-05-25) — inline follow-up chat on deep-search results.
// The contract these tests pin: when the user sends a follow-up, the
// request body MUST include view_context.deep_search_query so the chat
// backend can ground the answer in the prior search context.

describe("DeepSearchFollowupChat", () => {
  const baseProps = {
    searchQuery: "EU carbon border adjustment 2026 impact",
    searchAnswer: "CBAM phased rollout begins Q3 2026; affects steel, aluminium…",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders the entry button when closed", () => {
    render(<DeepSearchFollowupChat {...baseProps} />);
    expect(
      screen.getByRole("button", { name: /Ask a follow-up about this result/i })
    ).toBeInTheDocument();
  });

  it("opens the input on click + shows the textarea", async () => {
    render(<DeepSearchFollowupChat {...baseProps} />);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Ask a follow-up about this result/i })
    );
    expect(screen.getByTestId("deep-search-followup-input")).toBeInTheDocument();
    expect(screen.getByTestId("deep-search-followup-send")).toBeDisabled();
  });

  it("POSTs to /api/chat with view_context.deep_search_query set", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        session_id: "sess-1",
        answer: "CBAM Phase 2 begins 2027 covering organic chemicals.",
        sources: [{ title: "EU Commission CBAM FAQ", source_name: "European Commission" }],
      }),
    });
    vi.stubGlobal("fetch", mockFetch);

    render(<DeepSearchFollowupChat {...baseProps} countryCode="DE" />);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Ask a follow-up about this result/i })
    );

    const input = screen.getByTestId("deep-search-followup-input");
    await user.type(input, "What about Phase 2 timelines?");
    await user.click(screen.getByTestId("deep-search-followup-send"));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const [, init] = mockFetch.mock.calls[0];
    const body = JSON.parse(init.body);
    expect(body.question).toBe("What about Phase 2 timelines?");
    expect(body.view_context).toMatchObject({
      route: "/deep-search",
      deep_search_query: baseProps.searchQuery,
      country: "DE",
    });
    // Carries the prior answer as the label (truncated to 500 chars).
    expect(body.view_context.label).toContain("CBAM phased rollout");

    // Renders the assistant turn.
    await waitFor(() => {
      expect(
        screen.getByText(/CBAM Phase 2 begins 2027/i)
      ).toBeInTheDocument();
    });
  });

  it("threads session_id across multiple turns", async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          session_id: "sess-99",
          answer: "First answer.",
          sources: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          session_id: "sess-99",
          answer: "Second answer.",
          sources: [],
        }),
      });
    vi.stubGlobal("fetch", mockFetch);

    render(<DeepSearchFollowupChat {...baseProps} />);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Ask a follow-up about this result/i })
    );

    const input = screen.getByTestId("deep-search-followup-input");

    await user.type(input, "First question?");
    await user.click(screen.getByTestId("deep-search-followup-send"));
    await waitFor(() =>
      expect(screen.getByText(/First answer/)).toBeInTheDocument()
    );

    await user.type(input, "Second question?");
    await user.click(screen.getByTestId("deep-search-followup-send"));
    await waitFor(() =>
      expect(screen.getByText(/Second answer/)).toBeInTheDocument()
    );

    // Second call must carry session_id from the first response.
    const [, firstInit] = mockFetch.mock.calls[0];
    const [, secondInit] = mockFetch.mock.calls[1];
    expect(JSON.parse(firstInit.body).session_id).toBeNull();
    expect(JSON.parse(secondInit.body).session_id).toBe("sess-99");
  });

  it("surfaces 401 sign-in error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) })
    );
    render(<DeepSearchFollowupChat {...baseProps} />);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Ask a follow-up about this result/i })
    );
    await user.type(screen.getByTestId("deep-search-followup-input"), "Why?");
    await user.click(screen.getByTestId("deep-search-followup-send"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/Sign in to chat/i);
    });
  });

  it("surfaces 429 quota error with upgrade hint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 429, json: async () => ({}) })
    );
    render(<DeepSearchFollowupChat {...baseProps} />);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Ask a follow-up about this result/i })
    );
    await user.type(
      screen.getByTestId("deep-search-followup-input"),
      "Another follow-up?"
    );
    await user.click(screen.getByTestId("deep-search-followup-send"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/Free tier chat quota/i);
    });
  });
});
