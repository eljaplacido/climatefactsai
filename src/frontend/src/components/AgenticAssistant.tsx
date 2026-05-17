"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Sparkles,
  Loader2,
  MapPin,
  BookOpen,
  Search,
  MessageCircle,
  ChevronDown,
  Mic,
} from "lucide-react";
import Markdown from "./Markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
  highlighted_countries?: string[];
  cited_articles?: { article_id: string; title: string }[];
  clarification_needed?: string[];
  mode?: string;
}

interface AgenticAssistantProps {
  currentPage?: string;
  currentArticleId?: string;
  currentCountry?: string;
  currentAnalysisId?: string;
  currentDeepSearchQuery?: string;
  currentCompareCountries?: string[];
  currentSourceId?: string;
  currentRoute?: string;
  contextLabel?: string;
  onHighlightCountries?: (countries: string[]) => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const MODE_LABELS: Record<string, { label: string; icon: typeof MapPin }> = {
  map_intelligence: { label: "Map Intelligence", icon: MapPin },
  article_qa: { label: "Article Analysis", icon: BookOpen },
  research_analysis: { label: "Research", icon: Search },
  general: { label: "General", icon: MessageCircle },
};

const EXAMPLE_QUERIES: Record<string, string[]> = {
  map: [
    "Biggest climate risks in Southeast Asia?",
    "Compare renewable energy: Europe vs Asia",
    "Countries with rising temperature anomalies",
    "African nations with most climate coverage?",
  ],
  articles: [
    "How does this compare to other findings?",
    "What are the key scientific claims here?",
    "Is this source reliable for climate reporting?",
    "Explain the transparency scores for this article",
  ],
  "deep-search": [
    "Compare drought in southern vs northern Europe",
    "How has Arctic ice changed since 2020?",
    "Renewable energy progress: EU vs China",
    "Help me understand how deep search works",
  ],
  feed: [
    "What source types should I follow?",
    "Help me set up my feed preferences",
    "What are the most reliable climate sources?",
    "Explain the different update frequencies",
  ],
  transparency: [
    "Explain these credibility scores",
    "Why are some metrics not yet analyzed?",
    "How is the reliability score calculated?",
    "What does the evidence chain show?",
  ],
  sources: [
    "Which sources have the highest credibility?",
    "How can I suggest a new source?",
    "What types of sources does the platform use?",
    "Compare source reliability across regions",
  ],
  default: [
    "Latest climate trends globally?",
    "Summarize recent Arctic ice reports",
    "How does this platform work?",
    "What features are available?",
  ],
};

const PAGE_HELP: Record<string, string> = {
  map: "You're viewing the **Climate Map**. Click countries to see article coverage, source details, and climate risk indicators. Use filters to narrow by date, source, category, or keyword. Switch layers to see temperature anomalies, climate risk, or source diversity.",
  "deep-search": "You're on **Deep Search**. Enter a climate question to get AI-synthesized answers from our article corpus + external research sources. Use Compare mode to analyze two topics side by side. Weather data is included automatically for climate queries.",
  feed: "You're on **My Feed**. Configure which countries, source types, and topics you want to follow. Choose from climate news, weather anomalies, research releases, industry reports, and more. Set your update frequency to get notified on your schedule.",
  articles: "You're viewing an **Article**. Each article shows credibility scores, extracted claims, and fact-check status. Click Transparency to see the full analysis breakdown.",
  transparency: "You're viewing a **Transparency Report**. This shows how the article was analyzed: confidence scores, source reliability, claim verification status, and evidence chains. Amber sections are still being processed.",
  sources: "You're on the **Sources** page. Browse all data sources the platform monitors. Each source has a reliability tier and coverage area. You can suggest new sources for the platform admins to review.",
  default: "Welcome to **Climatefacts.ai** - your climate intelligence platform. Explore the map, search articles, analyze URLs, configure your feed, and get AI-powered insights across all features.",
};

export default function AgenticAssistant({
  currentPage = "default",
  currentArticleId,
  currentCountry,
  currentAnalysisId,
  currentDeepSearchQuery,
  currentCompareCountries,
  currentSourceId,
  currentRoute,
  contextLabel,
  onHighlightCountries,
}: AgenticAssistantProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isExpanded) {
      // Small delay to let the animation start, then focus
      const timer = setTimeout(() => inputRef.current?.focus(), 150);
      return () => clearTimeout(timer);
    }
  }, [isExpanded]);

  // Close on click outside when expanded
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        isExpanded &&
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        // Only collapse if there are no messages (preserve chat context)
        if (messages.length === 0) {
          setIsExpanded(false);
        }
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isExpanded, messages.length]);

  const determineMode = (): string => {
    if (currentPage === "map") return "map_intelligence";
    if (currentArticleId) return "article_qa";
    if (currentPage === "research") return "research_analysis";
    return "general";
  };

  const mode = determineMode();
  const modeInfo = MODE_LABELS[mode] || MODE_LABELS.general;
  const ModeIcon = modeInfo.icon;

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text || loading) return;

    const userMessage: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("clilens_token")
          : null;

      // Single object describing what the user is currently looking at; the
      // backend hydrates this server-side (article text, country stats, URL
      // analysis row, etc.) and feeds it into the LLM system prompt so the
      // model can resolve "this article", "this country", etc.
      const viewContext: Record<string, any> = {};
      if (currentRoute) viewContext.route = currentRoute;
      else if (currentPage) viewContext.route = `/${currentPage === "default" ? "" : currentPage}`;
      if (currentArticleId) viewContext.article_id = currentArticleId;
      if (currentCountry) viewContext.country = currentCountry;
      if (currentCompareCountries && currentCompareCountries.length > 0) {
        viewContext.compare_countries = currentCompareCountries;
      }
      if (currentAnalysisId) viewContext.analysis_id = currentAnalysisId;
      if (currentDeepSearchQuery) viewContext.deep_search_query = currentDeepSearchQuery;
      if (currentSourceId) viewContext.source_id = currentSourceId;
      if (contextLabel) viewContext.label = contextLabel;
      const hasViewContext = Object.keys(viewContext).length > 0;

      let endpoint = `${API_BASE}/api/chat`;
      let body: Record<string, any> = {
        question: userMessage.content,
        mode,
        session_id: sessionId,
      };
      if (currentCountry) body.country = currentCountry;
      if (hasViewContext) body.view_context = viewContext;

      if (mode === "map_intelligence") {
        endpoint = `${API_BASE}/api/map/query`;
        body = {
          query: userMessage.content,
          session_id: sessionId,
          limit: 10,
        };
        if (currentCountry) {
          body.countries = [currentCountry];
        }
        if (hasViewContext) body.view_context = viewContext;
      } else if (mode === "article_qa" && currentArticleId) {
        endpoint = `${API_BASE}/api/articles/${currentArticleId}/ask`;
        body = {
          question: userMessage.content,
          conversation_context: messages.slice(-4).map((m) => ({
            role: m.role,
            content: m.content,
          })),
        };
        if (hasViewContext) body.view_context = viewContext;
      }

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();

      const assistantMessage: Message = {
        role: "assistant",
        content:
          data.answer ||
          data.response ||
          data.text ||
          "No response generated.",
        mode,
      };

      if (Array.isArray(data.highlighted_countries)) {
        assistantMessage.highlighted_countries = data.highlighted_countries;
        onHighlightCountries?.(data.highlighted_countries);
      }

      if (Array.isArray(data.country_highlights)) {
        assistantMessage.highlighted_countries = data.country_highlights
          .map((h: any) => h?.country_code)
          .filter((cc: any): cc is string => typeof cc === "string" && cc.length > 0);
        onHighlightCountries?.(assistantMessage.highlighted_countries || []);
      }

      if (Array.isArray(data.clarification_needed) && data.clarification_needed.length > 0) {
        assistantMessage.clarification_needed = data.clarification_needed
          .filter((s: any): s is string => typeof s === "string" && s.length > 0)
          .slice(0, 5);
      }

      const rawSources = Array.isArray(data.sources)
        ? data.sources
        : Array.isArray(data.citations)
          ? data.citations
          : null;
      if (rawSources) {
        assistantMessage.cited_articles = rawSources
          .filter((s: any) => s && s.article_id)
          .slice(0, 5)
          .map((s: any) => ({
            article_id: s.article_id,
            title: s.title || s.source_name,
          }));
      }

      if (data.session_id) setSessionId(data.session_id);

      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I couldn't process that request. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleExampleClick = (query: string) => {
    setInput(query);
    inputRef.current?.focus();
  };

  const examples = EXAMPLE_QUERIES[currentPage] || EXAMPLE_QUERIES.default;

  return (
    <div
      ref={containerRef}
      className={`fixed bottom-0 left-1/2 -translate-x-1/2 z-50 w-full max-w-[620px] transition-all duration-300 ease-out ${
        isExpanded ? "px-3 sm:px-0" : "px-4 sm:px-0"
      }`}
    >
      {/* Expanded chat panel */}
      <div
        className={`overflow-hidden transition-all duration-300 ease-out ${
          isExpanded
            ? "max-h-[500px] opacity-100"
            : "max-h-0 opacity-0"
        }`}
      >
        <div className="bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 border-b-0 rounded-t-xl flex flex-col">
          {/* Header with context badge and collapse */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-700/50">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-teal-400" />
              <span className="text-sm font-semibold text-white">
                Climate Intelligence
              </span>
            </div>
            <div className="flex items-center gap-2">
              {/* Context mode badge */}
              <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-800 rounded-md border border-slate-600/50">
                <ModeIcon className="h-3 w-3 text-teal-400" />
                <span className="text-[11px] text-slate-300 font-medium">
                  {modeInfo.label}
                </span>
              </div>
              <button
                onClick={() => setIsExpanded(false)}
                className="p-1 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded transition-colors"
                aria-label="Minimize chat"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[120px] max-h-[340px] scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {messages.length === 0 && (
              <div className="py-3">
                {/* Page context help */}
                <div className="mb-3 px-3 py-2.5 bg-slate-800/80 border border-teal-500/20 rounded-lg">
                  <p className="text-xs text-slate-300 leading-relaxed">
                    <Markdown
                      content={PAGE_HELP[currentPage] || PAGE_HELP.default}
                      className="text-slate-300 [&_p]:text-slate-300 [&_strong]:text-teal-400 [&_p]:text-xs [&_p]:leading-relaxed"
                    />
                  </p>
                </div>
                <p className="text-[10px] text-slate-500 mb-2 text-center uppercase tracking-wide">
                  Try asking
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {examples.slice(0, 4).map((q) => (
                    <button
                      key={q}
                      onClick={() => handleExampleClick(q)}
                      className="text-[11px] px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-full border border-slate-700/50 hover:border-teal-500/40 transition-all"
                    >
                      {q}
                    </button>
                  ))}
                </div>
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
                      : "bg-slate-800 text-slate-200 border border-slate-700/50"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <Markdown content={msg.content} className="text-slate-200 [&_p]:text-slate-200 [&_strong]:text-white [&_a]:text-teal-400" />
                  ) : (
                    msg.content
                  )}
                  {msg.cited_articles && msg.cited_articles.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-600/50 space-y-1">
                      {msg.cited_articles.map((a) => (
                        <a
                          key={a.article_id}
                          href={`/articles/${a.article_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-xs text-teal-400 hover:text-teal-300 hover:underline truncate"
                          title="Opens in a new tab so this chat session is preserved"
                        >
                          {a.title}
                        </a>
                      ))}
                    </div>
                  )}
                  {msg.highlighted_countries &&
                    msg.highlighted_countries.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {msg.highlighted_countries.slice(0, 5).map((cc) => (
                          <span
                            key={cc}
                            className="inline-block px-1.5 py-0.5 bg-teal-900/50 text-teal-300 text-[10px] rounded border border-teal-700/50"
                          >
                            {cc}
                          </span>
                        ))}
                      </div>
                    )}
                  {msg.clarification_needed && msg.clarification_needed.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-amber-700/40">
                      <p className="text-[10px] uppercase tracking-wider text-amber-300 mb-1.5">
                        Try a more specific query
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {msg.clarification_needed.map((s) => (
                          <button
                            key={s}
                            type="button"
                            onClick={() => handleSend(s)}
                            className="px-2 py-1 rounded-full bg-amber-900/30 hover:bg-amber-800/50 text-amber-100 text-[11px] border border-amber-800/60 transition-colors"
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-slate-800 border border-slate-700/50 rounded-lg px-3 py-2 flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-teal-400" />
                  <span className="text-sm text-slate-400">Analyzing...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input area inside expanded panel */}
          <div className="px-4 py-3 border-t border-slate-700/50">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask about climate news, data, or trends..."
                className="flex-1 px-3 py-2 text-sm bg-slate-800 border border-slate-600/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500/50"
                disabled={loading}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || loading}
                className="p-2 bg-teal-600 text-white rounded-lg hover:bg-teal-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Collapsed bar - always visible at bottom */}
      <div
        onClick={() => !isExpanded && setIsExpanded(true)}
        className={`transition-all duration-300 ${
          isExpanded ? "hidden" : "block"
        }`}
      >
        <div className="h-12 bg-slate-900/95 backdrop-blur-xl border-t-2 border-teal-500/60 rounded-t-xl flex items-center px-4 gap-3 cursor-pointer hover:bg-slate-800/95 transition-colors shadow-lg shadow-black/20">
          <Sparkles className="h-4 w-4 text-teal-400 flex-shrink-0" />
          <span className="flex-1 text-sm text-slate-400 truncate">
            Ask about climate news, data, or trends...
          </span>
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Context badge on the bar */}
            <div className="hidden sm:flex items-center gap-1 px-2 py-0.5 bg-slate-800 rounded border border-slate-700/50">
              <ModeIcon className="h-3 w-3 text-teal-400" />
              <span className="text-[10px] text-slate-400 font-medium">
                {modeInfo.label}
              </span>
            </div>
            <Mic className="h-4 w-4 text-slate-500" />
          </div>
        </div>
      </div>
    </div>
  );
}
