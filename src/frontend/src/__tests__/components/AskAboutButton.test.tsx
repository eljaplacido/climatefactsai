import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AskAboutButton from "../../components/AskAboutButton";

describe("AskAboutButton — chat-as-heart step 2", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the inline variant with the ? icon", () => {
    render(<AskAboutButton prompt="Explain this metric" />);
    expect(screen.getByTestId("ask-about-inline")).toBeInTheDocument();
  });

  it("renders the chip variant with prompt text visible", () => {
    render(
      <AskAboutButton
        prompt="Why is this article low credibility?"
        variant="chip"
      />,
    );
    const btn = screen.getByTestId("ask-about-chip");
    expect(btn).toBeInTheDocument();
    expect(btn.textContent).toContain("Why is this article low credibility?");
  });

  it("dispatches the climatenews:assistant-prefill event on click", () => {
    const dispatched: CustomEvent[] = [];
    const orig = window.dispatchEvent;
    window.dispatchEvent = vi.fn((e: Event) => {
      dispatched.push(e as CustomEvent);
      return true;
    });

    render(<AskAboutButton prompt="What does scope 3 mean?" />);
    fireEvent.click(screen.getByTestId("ask-about-inline"));

    window.dispatchEvent = orig;

    const evt = dispatched.find((e) => e.type === "climatenews:assistant-prefill");
    expect(evt).toBeDefined();
    expect((evt as any).detail.prompt).toBe("What does scope 3 mean?");
  });

  it("uses ariaLabel override when provided", () => {
    render(
      <AskAboutButton
        prompt="Explain this credibility score"
        ariaLabel="Explain credibility"
      />,
    );
    expect(screen.getByLabelText("Explain credibility")).toBeInTheDocument();
  });

  it("stopPropagation prevents click bubbling (so it works inside clickable cards)", () => {
    const parentClick = vi.fn();
    render(
      <div onClick={parentClick} data-testid="parent">
        <AskAboutButton prompt="Why?" />
      </div>,
    );
    fireEvent.click(screen.getByTestId("ask-about-inline"));
    expect(parentClick).not.toHaveBeenCalled();
  });
});
