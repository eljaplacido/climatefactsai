import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useSave } from "@/lib/useSave";
import type { SavedItemType } from "@/types";

// Slice 3 (2026-05-25) — the useSave hook is the single backend
// touchpoint for all 8 save types. These tests pin the request shape
// it issues per type + the error-handling matrix.

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

function Harness(props: {
  type: SavedItemType;
  id?: string;
  itemRef?: string;
  label?: string;
}) {
  const { saved, busy, error, toggle } = useSave({
    type: props.type,
    id: props.id,
    itemRef: props.itemRef,
    label: props.label,
  });
  return (
    <div>
      <span data-testid="saved">{saved ? "yes" : "no"}</span>
      <span data-testid="busy">{busy ? "yes" : "no"}</span>
      <span data-testid="error">{error ?? ""}</span>
      <button onClick={toggle}>toggle</button>
    </div>
  );
}

describe("useSave", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockCheckSavedItem.mockResolvedValue({ saved: false, saved_id: null });
    mockCreateSavedItem.mockResolvedValue({ message: "ok", item_type: "company" });
    mockDeleteSavedItem.mockResolvedValue({ message: "ok" });
  });

  describe("request shape per type", () => {
    it("issues item_id for FK-able types (company)", async () => {
      localStorage.setItem("clilens_token", "tk");
      render(<Harness type="company" id="cmp-1" label="Acme Corp" />);
      await waitFor(() => expect(mockCheckSavedItem).toHaveBeenCalled());

      const user = userEvent.setup();
      await user.click(screen.getByText("toggle"));

      await waitFor(() => expect(mockCreateSavedItem).toHaveBeenCalled());
      const req = mockCreateSavedItem.mock.calls[0][0];
      expect(req.item_type).toBe("company");
      expect(req.item_id).toBe("cmp-1");
      expect(req.item_ref).toBeNull();
      expect(req.label).toBe("Acme Corp");
    });

    it("issues item_ref for text-keyed types (country)", async () => {
      localStorage.setItem("clilens_token", "tk");
      render(<Harness type="country" itemRef="DE" label="Germany" />);
      await waitFor(() => expect(mockCheckSavedItem).toHaveBeenCalled());

      const user = userEvent.setup();
      await user.click(screen.getByText("toggle"));

      await waitFor(() => expect(mockCreateSavedItem).toHaveBeenCalled());
      const req = mockCreateSavedItem.mock.calls[0][0];
      expect(req.item_type).toBe("country");
      expect(req.item_ref).toBe("DE");
      expect(req.item_id).toBeNull();
    });

    it("issues item_ref for deep_search type", async () => {
      localStorage.setItem("clilens_token", "tk");
      render(<Harness type="deep_search" itemRef="climate-finance Q3 2026" />);
      await waitFor(() => expect(mockCheckSavedItem).toHaveBeenCalled());

      const user = userEvent.setup();
      await user.click(screen.getByText("toggle"));

      await waitFor(() => expect(mockCreateSavedItem).toHaveBeenCalled());
      expect(mockCreateSavedItem.mock.calls[0][0].item_type).toBe("deep_search");
      expect(mockCreateSavedItem.mock.calls[0][0].item_ref).toBe(
        "climate-finance Q3 2026"
      );
    });
  });

  describe("anonymous path", () => {
    it("toggles cache-only without API calls", async () => {
      render(<Harness type="article" id="a-1" />);

      const user = userEvent.setup();
      await user.click(screen.getByText("toggle"));

      expect(screen.getByTestId("saved")).toHaveTextContent("yes");
      expect(mockCheckSavedItem).not.toHaveBeenCalled();
      expect(mockCreateSavedItem).not.toHaveBeenCalled();
      expect(localStorage.getItem("clilens-saved:article:a-1")).toBe("1");
    });
  });

  describe("error handling", () => {
    it("reverts state + surfaces 429 quota message", async () => {
      localStorage.setItem("clilens_token", "tk");
      mockCreateSavedItem.mockRejectedValue({
        response: {
          status: 429,
          data: {
            detail: {
              message: "Free tier saves up to 3 articles. Upgrade for unlimited.",
              limit: 3,
              tier: "free",
            },
          },
        },
      });

      render(<Harness type="article" id="a-1" />);
      await waitFor(() => expect(mockCheckSavedItem).toHaveBeenCalled());

      const user = userEvent.setup();
      await user.click(screen.getByText("toggle"));

      await waitFor(() => {
        expect(screen.getByTestId("error")).toHaveTextContent(
          /Free tier saves up to 3 articles/
        );
      });
      // Reverted optimistic toggle.
      expect(screen.getByTestId("saved")).toHaveTextContent("no");
    });

    it("reverts state + surfaces 401 sign-in prompt", async () => {
      localStorage.setItem("clilens_token", "stale");
      mockCheckSavedItem.mockResolvedValue({ saved: false, saved_id: null });
      mockCreateSavedItem.mockRejectedValue({ response: { status: 401 } });

      render(<Harness type="company" id="c-1" />);
      await waitFor(() => expect(mockCheckSavedItem).toHaveBeenCalled());

      const user = userEvent.setup();
      await user.click(screen.getByText("toggle"));

      await waitFor(() => {
        expect(screen.getByTestId("error")).toHaveTextContent(/Sign in to save/);
      });
    });
  });

  describe("delete path", () => {
    it("calls deleteSavedItem with the saved_id from initial check", async () => {
      localStorage.setItem("clilens_token", "tk");
      mockCheckSavedItem.mockResolvedValue({
        saved: true,
        saved_id: "sv-uuid-9",
      });

      render(<Harness type="company" id="c-1" />);
      await waitFor(() =>
        expect(screen.getByTestId("saved")).toHaveTextContent("yes")
      );

      const user = userEvent.setup();
      await user.click(screen.getByText("toggle"));

      await waitFor(() => {
        expect(mockDeleteSavedItem).toHaveBeenCalledWith("sv-uuid-9");
      });
      expect(screen.getByTestId("saved")).toHaveTextContent("no");
    });
  });
});
