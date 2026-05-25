import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BookmarkButton from "@/components/BookmarkButton";

// Slice 3 (2026-05-25) — BookmarkButton was migrated off the legacy
// /api/user/bookmarks/{id} endpoint to the polymorphic /api/user/saved
// surface via the useSave hook. Tests now mock the polymorphic API methods.

const mockCheckSavedItem = vi.fn();
const mockCreateSavedItem = vi.fn();
const mockDeleteSavedItem = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    checkSavedItem: (...args: any[]) => mockCheckSavedItem(...args),
    createSavedItem: (...args: any[]) => mockCreateSavedItem(...args),
    deleteSavedItem: (...args: any[]) => mockDeleteSavedItem(...args),
  },
}));

describe("BookmarkButton (post Slice 3 migration)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockCheckSavedItem.mockResolvedValue({ saved: false, saved_id: null });
    mockCreateSavedItem.mockResolvedValue({ message: "ok", item_type: "article" });
    mockDeleteSavedItem.mockResolvedValue({ message: "ok" });
  });

  it("uses local cache when unauthenticated — no API calls", async () => {
    render(<BookmarkButton articleId="a-1" />);
    const user = userEvent.setup();

    const button = screen.getByRole("button");
    await user.click(button);

    expect(button).toHaveTextContent("Saved");
    expect(mockCheckSavedItem).not.toHaveBeenCalled();
    expect(mockCreateSavedItem).not.toHaveBeenCalled();

    // useSave persists per-item cache keys, not a single bookmarks blob.
    expect(localStorage.getItem("clilens-saved:article:a-1")).toBe("1");
  });

  it("hydrates saved state from /api/user/saved/check when authenticated", async () => {
    localStorage.setItem("clilens_token", "token-123");
    mockCheckSavedItem.mockResolvedValue({
      saved: true,
      saved_id: "saved-uuid-1",
    });

    render(<BookmarkButton articleId="a-1" />);

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Saved");
    });

    expect(mockCheckSavedItem).toHaveBeenCalledWith({
      item_type: "article",
      item_id: "a-1",
      item_ref: undefined,
    });
    expect(localStorage.getItem("clilens-saved:article:a-1")).toBe("1");
  });

  it("calls createSavedItem with the polymorphic shape on save", async () => {
    localStorage.setItem("clilens_token", "token-123");
    mockCheckSavedItem.mockResolvedValue({ saved: false, saved_id: null });

    render(<BookmarkButton articleId="a-1" />);

    // Wait for initial check to settle so subsequent click is not racing.
    await waitFor(() => expect(mockCheckSavedItem).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockCreateSavedItem).toHaveBeenCalledWith(
        expect.objectContaining({
          item_type: "article",
          item_id: "a-1",
        })
      );
    });
  });

  it("calls deleteSavedItem with the saved_id on unsave", async () => {
    localStorage.setItem("clilens_token", "token-123");
    mockCheckSavedItem.mockResolvedValue({
      saved: true,
      saved_id: "saved-uuid-1",
    });

    render(<BookmarkButton articleId="a-1" />);
    await waitFor(() =>
      expect(screen.getByRole("button")).toHaveTextContent("Saved")
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockDeleteSavedItem).toHaveBeenCalledWith("saved-uuid-1");
    });
  });

  it("surfaces 429 quota error inline", async () => {
    localStorage.setItem("clilens_token", "token-123");
    mockCheckSavedItem.mockResolvedValue({ saved: false, saved_id: null });
    mockCreateSavedItem.mockRejectedValue({
      response: {
        status: 429,
        data: { detail: { message: "Free tier saves up to 3 articles. Upgrade for unlimited." } },
      },
    });

    render(<BookmarkButton articleId="a-1" />);
    await waitFor(() => expect(mockCheckSavedItem).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /Free tier saves up to 3 articles/
      );
    });
    // State should revert (button back to "Save").
    expect(screen.getByRole("button")).toHaveTextContent("Save");
  });
});
