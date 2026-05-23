import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BookmarkButton from "@/components/BookmarkButton";

const mockGetBookmarkStatus = vi.fn();
const mockCreateBookmark = vi.fn();
const mockDeleteBookmark = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getBookmarkStatus: (...args: any[]) => mockGetBookmarkStatus(...args),
    createBookmark: (...args: any[]) => mockCreateBookmark(...args),
    deleteBookmark: (...args: any[]) => mockDeleteBookmark(...args),
  },
}));

describe("BookmarkButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockGetBookmarkStatus.mockResolvedValue({ article_id: "a-1", bookmarked: false });
    mockCreateBookmark.mockResolvedValue({ message: "ok", article_id: "a-1" });
    mockDeleteBookmark.mockResolvedValue({ message: "ok" });
  });

  it("uses local bookmarks when unauthenticated", async () => {
    render(<BookmarkButton articleId="a-1" />);
    const user = userEvent.setup();

    const button = screen.getByRole("button");
    await user.click(button);

    expect(button).toHaveTextContent("Saved");
    expect(mockGetBookmarkStatus).not.toHaveBeenCalled();
    expect(mockCreateBookmark).not.toHaveBeenCalled();

    const stored = JSON.parse(localStorage.getItem("clilens-bookmarks") || "[]");
    expect(stored).toEqual(["a-1"]);
  });

  it("hydrates saved state from backend for authenticated users", async () => {
    localStorage.setItem("clilens_token", "token-123");
    mockGetBookmarkStatus.mockResolvedValue({ article_id: "a-1", bookmarked: true });

    render(<BookmarkButton articleId="a-1" />);

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Saved");
    });

    expect(mockGetBookmarkStatus).toHaveBeenCalledWith("a-1");
    const stored = JSON.parse(localStorage.getItem("clilens-bookmarks") || "[]");
    expect(stored).toContain("a-1");
  });

  it("creates bookmark via backend when authenticated", async () => {
    localStorage.setItem("clilens_token", "token-123");
    mockGetBookmarkStatus.mockResolvedValue({ article_id: "a-1", bookmarked: false });

    render(<BookmarkButton articleId="a-1" />);
    const user = userEvent.setup();
    const button = screen.getByRole("button");

    await user.click(button);

    await waitFor(() => {
      expect(mockCreateBookmark).toHaveBeenCalledWith("a-1");
      expect(button).toHaveTextContent("Saved");
    });
  });

  it("reverts optimistic state if backend save fails", async () => {
    localStorage.setItem("clilens_token", "token-123");
    mockGetBookmarkStatus.mockResolvedValue({ article_id: "a-1", bookmarked: false });
    mockCreateBookmark.mockRejectedValue(new Error("save failed"));

    render(<BookmarkButton articleId="a-1" />);
    const user = userEvent.setup();
    const button = screen.getByRole("button");

    await user.click(button);

    await waitFor(() => {
      expect(button).toHaveTextContent("Save");
    });

    const stored = JSON.parse(localStorage.getItem("clilens-bookmarks") || "[]");
    expect(stored).toEqual([]);
  });
});
