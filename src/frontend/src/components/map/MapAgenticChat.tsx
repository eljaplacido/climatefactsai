"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  MessageCircle,
  Send,
  X,
  ChevronDown,
  ChevronUp,
  Loader2,
  ExternalLink,
  Sparkles,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const EXAMPLE_CHIPS = [
  "Drought in East Africa",
  "Arctic ice trends",
  "Renewable energy in Europe",
  "Climate policy in Asia",
];

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  cited_articles?: {
    article_id: string;
    title: string;
    source_name?: string;
  }[];
  highlighted_countries?: string[];
}

interface MapAgenticChatProps {
  onHighlightCountries: (codes: string[]) => void;
  onCountryClick?: (code: string) => void;
  selectedCountry?: string | null;
  compareCountries?: string[];
}

export default function MapAgenticChat({
  onHighlightCountries,
  onCountryClick,
  selectedCountry,
  compareCountries,
}: MapAgenticChatProps) {
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  // Corpus-only (default), external web search, or both — so the chat can
  // answer broad questions even when no platform article matches.
  const [sourceMode, setSourceMode] = useState<"platform" | "web" | "both">("platform");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => {
    if (expanded && inputRef.current) {
      inputRef.current.focus();
    }
  }, [expanded]);

  const sendQuery = useCallback(
    async (queryText: string) => {
      if (!queryText.trim() || loading) return;

      const userMessage: ChatMessage = { role: "user", content: queryText };
      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setLoading(true);

      try {
        const viewContext: Record<string, any> = { route: "/map" };
        if (selectedCountry) viewContext.country = selectedCountry;
        if (compareCountries && compareCountries.length > 0) {
          viewContext.compare_countries = compareCountries;
        }

        const requestBody: Record<string, any> = {
          query: queryText,
          session_id: sessionId,
          limit: 30,
          view_context: viewContext,
          source_mode: sourceMode,
        };
        if (selectedCountry) requestBody.countries = [selectedCountry];

        const res = await fetch(`${API_BASE}/api/map/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        });

        if (res.ok) {
          const data = await res.json();

          // Store session_id for follow-up queries
          if (data.session_id) {
            setSessionId(data.session_id);
          }

          const highlightedCodes: string[] = (
            data.country_highlights || []
          ).map((h: any) => h.country_code);

          const citedArticles = (data.matching_articles_detail || [])
            .slice(0, 5)
            .map((a: any) => ({
              article_id: a.article_id,
              title: a.title,
              source_name: a.source_name,
            }));

          const assistantMessage: ChatMessage = {
            role: "assistant",
            content:
              data.answer ||
              `Found ${data.matching_articles || 0} articles across ${highlightedCodes.length} countries.`,
            cited_articles: citedArticles,
            highlighted_countries: highlightedCodes,
          };

          setMessages((prev) => [...prev, assistantMessage]);
          onHighlightCountries(highlightedCodes);
        } else {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content:
                "Sorry, I could not process your query. Please try rephrasing it.",
            },
          ]);
        }
      } catch (err) {
        console.error("Chat query failed:", err);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "An error occurred while processing your query. Please try again.",
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [loading, sessionId, onHighlightCountries, selectedCountry, compareCountries, sourceMode]
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendQuery(input);
  }

  function handleChipClick(chip: string) {
    if (!expanded) setExpanded(true);
    sendQuery(chip);
  }

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] w-full max-w-2xl px-4">
      <div className="bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700 shadow-2xl overflow-hidden">
        {/* Expand/collapse toggle */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-700/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-teal-400" />
            <span className="text-sm font-medium text-slate-200">
              Climate Intelligence Chat
            </span>
            {messages.length > 0 && (
              <span className="text-[10px] bg-teal-600/30 text-teal-300 px-1.5 py-0.5 rounded-full">
                {messages.length} messages
              </span>
            )}
          </div>
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronUp className="h-4 w-4 text-slate-400" />
          )}
        </button>

        {expanded && (
          <>
            {/* Messages */}
            <div className="max-h-64 overflow-y-auto px-4 py-3 space-y-3 border-t border-slate-700">
              {messages.length === 0 && (
                <div className="text-center py-4">
                  <Sparkles className="h-6 w-6 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-500">
                    Ask questions about climate news, countries, and trends.
                    Results will be highlighted on the map.
                  </p>
                </div>
              )}

              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                      msg.role === "user"
                        ? "bg-teal-600 text-white"
                        : "bg-slate-700 text-slate-200"
                    }`}
                  >
                    {msg.role === "assistant" ? (
                      <div className="prose prose-sm prose-invert max-w-none">
                        <ReactMarkdown
                          components={{
                            p: ({ children }) => (
                              <p className="text-sm text-slate-200 mb-1.5 last:mb-0">
                                {children}
                              </p>
                            ),
                            strong: ({ children }) => (
                              <strong className="text-teal-300 font-semibold">
                                {children}
                              </strong>
                            ),
                            ul: ({ children }) => (
                              <ul className="text-sm text-slate-300 pl-4 mb-1.5 list-disc">
                                {children}
                              </ul>
                            ),
                            li: ({ children }) => (
                              <li className="mb-0.5">{children}</li>
                            ),
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p>{msg.content}</p>
                    )}

                    {/* Cited articles */}
                    {msg.cited_articles && msg.cited_articles.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-600 space-y-1">
                        <p className="text-[10px] text-slate-400 uppercase tracking-wider">
                          Sources
                        </p>
                        {msg.cited_articles.map((article) => (
                          <a
                            key={article.article_id}
                            href={`/articles/${article.article_id}`}
                            className="flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 transition-colors"
                          >
                            <ExternalLink className="h-2.5 w-2.5 flex-shrink-0" />
                            <span className="truncate">{article.title}</span>
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Highlighted countries */}
                    {msg.highlighted_countries &&
                      msg.highlighted_countries.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {msg.highlighted_countries.map((cc) => (
                            <button
                              key={cc}
                              type="button"
                              onClick={() => onCountryClick?.(cc)}
                              className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30 hover:bg-amber-500/30 transition-colors cursor-pointer"
                            >
                              {cc}
                            </button>
                          ))}
                        </div>
                      )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-slate-700 rounded-lg px-3 py-2 flex items-center gap-2">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                    <span className="text-xs text-slate-400">Analyzing...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Example chips */}
            {messages.length === 0 && (
              <div className="px-4 pb-2 flex flex-wrap gap-1.5">
                {EXAMPLE_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => handleChipClick(chip)}
                    className="text-xs bg-slate-700 text-slate-300 px-2.5 py-1 rounded-full border border-slate-600 hover:bg-slate-600 hover:text-slate-100 transition-colors"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            )}

            {/* Source mode toggle */}
            <div className="flex items-center gap-1.5 px-4 pt-3" role="group" aria-label="Answer source">
              <span className="text-[11px] text-slate-400 mr-1">Answer from:</span>
              {([
                { key: "platform", label: "Platform" },
                { key: "web", label: "Web" },
                { key: "both", label: "Both" },
              ] as const).map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setSourceMode(opt.key)}
                  aria-pressed={sourceMode === opt.key}
                  className={`px-2 py-0.5 text-[11px] rounded-full border transition-colors ${
                    sourceMode === opt.key
                      ? "bg-teal-600 text-white border-teal-500"
                      : "bg-slate-800 text-slate-300 border-slate-600 hover:bg-slate-700"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Input */}
            <form
              onSubmit={handleSubmit}
              className="flex items-center gap-2 px-4 py-3 border-t border-slate-700"
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about climate news..."
                disabled={loading}
                className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-teal-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="p-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
