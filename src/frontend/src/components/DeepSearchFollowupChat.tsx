"use client";

import { useState, useRef, useEffect } from "react";
import { MessageCircle, Send, Loader2, AlertCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// Slice 6 (2026-05-25, Honest-Gap-Audit v2 item 5) — inline follow-up
// chat on the deep-search result. Previously the only affordance was an
// "Ask about this result in chat" button that bounced to the global
// assistant — fire-and-forget, no iteration. Now the user can ask
// follow-ups inline and the thread carries forward via session_id +
// view_context.deep_search_query so the backend has context.

interface Turn {
  question: string;
  answer: string;
  sources?: Array<{ title?: string; source_name?: string }>;
}

interface DeepSearchFollowupChatProps {
  searchQuery: string;
  searchAnswer: string;
  /** Optional context to pass through view_context. */
  countryCode?: string;
}

export default function DeepSearchFollowupChat({
  searchQuery,
  searchAnswer,
  countryCode,
}: DeepSearchFollowupChatProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [thread, setThread] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // jsdom doesn't implement scrollIntoView — guard so tests don't blow up.
    if (typeof threadEndRef.current?.scrollIntoView === "function") {
      threadEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [thread.length]);

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    if (question.length < 3) {
      setError("Question too short.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const token =
        typeof window !== "undefined" ? localStorage.getItem("clilens_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question,
          session_id: sessionId,
          view_context: {
            route: "/deep-search",
            deep_search_query: searchQuery,
            // Truncate so we don't blow the chat prompt — the backend
            // can re-fetch the full answer from session memory if needed.
            label: searchAnswer.slice(0, 500),
            ...(countryCode ? { country: countryCode } : {}),
          },
        }),
      });

      if (!resp.ok) {
        if (resp.status === 401) {
          setError("Sign in to chat about your search results.");
          return;
        }
        if (resp.status === 429) {
          setError("Free tier chat quota reached. Upgrade for unlimited follow-ups.");
          return;
        }
        setError(`Chat failed (HTTP ${resp.status}). Try again.`);
        return;
      }

      const data = await resp.json();
      setSessionId(data.session_id || sessionId);
      setThread((prev) => [
        ...prev,
        {
          question,
          answer: data.answer || "(no answer returned)",
          sources: data.sources || [],
        },
      ]);
      setInput("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Network error.");
    } finally {
      setBusy(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Cmd/Ctrl + Enter submits — same convention as the global assistant.
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="mt-4 pt-3 border-t border-gray-100 dark:border-slate-800" data-testid="deep-search-followup">
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="text-xs text-teal-700 dark:text-teal-300 hover:text-teal-900 dark:hover:text-teal-200 flex items-center gap-1.5"
        >
          <MessageCircle className="w-3.5 h-3.5" />
          Ask a follow-up about this result
        </button>
      )}

      {open && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-gray-600 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <MessageCircle className="w-3.5 h-3.5" />
              Follow-up conversation
            </span>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setThread([]);
                setSessionId(null);
              }}
              className="text-gray-500 hover:text-gray-700 dark:text-slate-500 dark:hover:text-slate-300"
            >
              Close
            </button>
          </div>

          {thread.length > 0 && (
            <ul className="space-y-3 max-h-96 overflow-y-auto">
              {thread.map((turn, i) => (
                <li key={i} className="space-y-1.5">
                  <div className="text-xs font-medium text-gray-900 dark:text-slate-100">
                    Q: {turn.question}
                  </div>
                  <div className="text-sm text-gray-700 dark:text-slate-200 whitespace-pre-wrap bg-gray-50 dark:bg-slate-800/60 rounded p-2.5">
                    {turn.answer}
                  </div>
                  {turn.sources && turn.sources.length > 0 && (
                    <p className="text-[11px] text-gray-500 dark:text-slate-400">
                      {turn.sources.length} source
                      {turn.sources.length !== 1 ? "s" : ""}
                    </p>
                  )}
                </li>
              ))}
              <div ref={threadEndRef} />
            </ul>
          )}

          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything — sources, methodology, follow-up angles…"
              rows={2}
              disabled={busy}
              className="flex-1 resize-none rounded border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-sm text-gray-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-teal-500 disabled:opacity-60"
              data-testid="deep-search-followup-input"
            />
            <button
              type="button"
              onClick={send}
              disabled={busy || input.trim().length < 3}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-40 disabled:cursor-not-allowed"
              data-testid="deep-search-followup-send"
            >
              {busy ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Send className="w-3 h-3" />
              )}
              {busy ? "Asking…" : "Ask"}
            </button>
          </div>

          {error && (
            <p
              className="text-xs text-amber-700 dark:text-amber-300 flex items-center gap-1"
              role="alert"
            >
              <AlertCircle className="w-3 h-3" />
              {error}
            </p>
          )}

          <p className="text-[10px] text-gray-400 dark:text-slate-500">
            Cmd/Ctrl + Enter to send · context: deep-search query carried forward
          </p>
        </div>
      )}
    </div>
  );
}
