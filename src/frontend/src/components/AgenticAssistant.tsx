"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
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
import AIProvenanceBadge from "./AIProvenanceBadge";
import ChatActionConfirmModal from "./ChatActionConfirmModal";
import {
  dispatchChatAction,
  ACTION_MODES,
  type ChatActionSpec,
} from "@/lib/chatActionDispatcher";

interface Message {
  role: "user" | "assistant";
  content: string;
  highlighted_countries?: string[];
  cited_articles?: { article_id: string; title: string }[];
  clarification_needed?: string[];
  mode?: string;
  actions?: ChatActionSpec[];
}

interface AgenticAssistantProps {
  currentPage?: string;
  currentArticleId?: string;
  currentCountry?: string;
  currentAnalysisId?: string;
  currentDeepSearchQuery?: string;
  currentDeepSearchCompare?: { query_a: string; query_b: string };
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

// Slice 3 / chat-as-heart (2026-05-27) — context-aware prompts.
// Each page exposes 3-5 starter prompts; some intentionally nudge the
// LLM to invoke the 7 newly-wired skills (flag_off_topic, explore_entity,
// explain_connection, explore_sdg, tag_sdgs, promote_golden_example,
// suggest_company) so the agentic surface is actually discoverable.
const EXAMPLE_QUERIES: Record<string, string[]> = {
  map: [
    "Biggest climate risks in Southeast Asia?",
    "Compare renewable energy: Europe vs Asia",
    "Countries with rising temperature anomalies",
    "Which UN SDGs is this country aligned with?",      // -> explore_sdg / tag_sdgs
  ],
  articles: [
    "What are the key scientific claims here?",
    "Why is this source rated this way?",
    "How does this article connect to others on the topic?", // -> explain_connection
    "Flag this article as off-topic",                    // -> flag_off_topic
    "This is a great example — mark it as golden",       // -> promote_golden_example
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
    "Subscribe me to new IPCC papers",                   // -> subscribe_research_topic
    "Save this filter as a custom feed",                 // -> save_item
  ],
  transparency: [
    "Explain these credibility scores",
    "Why are some metrics not yet analyzed?",
    "What evidence supports the high-credibility verdict?",
    "Submit a calibration rating for this analysis",     // -> start_calibration_label
  ],
  sources: [
    "Which sources have the highest credibility?",
    "Compare source reliability across regions",
    "Suggest a new climate-news source",
    "What does T1 / T2 / T3 actually mean?",
  ],
  // Slice 3 additions — pages that previously had no suggestions
  companies: [
    "Show me SBTi-validated companies in Europe",
    "Verify Apple's 100% renewable electricity claim",   // -> verify_corporate_claim
    "Suggest a new company for the Tracker",             // -> suggest_company
    "Analyze Shell's latest sustainability report",      // -> analyze_corporate_report
  ],
  research: [
    "Subscribe me to new papers on CBAM compliance",     // -> subscribe_research_topic
    "Compare conclusions across recent ocean-warming papers",
    "Which papers have the highest methodology scores?",
    "Mark this analysis as a golden example",            // -> promote_golden_example
  ],
  saves: [
    "What have I saved this week?",
    "Help me organize my saved articles",
    "Which of my saves are no longer current?",
  ],
  sdg: [
    "Show me every article tagged Climate Action (SDG 13)", // -> explore_sdg
    "What does Goal 7 cover?",
    "Tag this text with the relevant SDGs",              // -> tag_sdgs
  ],
  explore: [
    "Show me every article that mentions this entity",
    "Why are these entities connected?",                 // -> explain_connection
    "What companies are linked to this concept?",
  ],
  country: [
    "What climate projections does IPCC AR6 give this country?", // -> explore_scenario
    "Show all SDGs this country is aligned with",        // -> explore_sdg
    "Compare this country to its regional peers",
    "What's the temperature anomaly here?",
  ],
  analyze: [
    "Explain what credibility means for this URL",
    "Submit a calibration label for this analysis",      // -> start_calibration_label
    "Help me interpret the per-claim verdicts",
  ],
  methodology: [
    "Explain the 3-axis source scoring",
    "How are claims extracted from articles?",
    "What's the ECGT rule for corporate offset claims?",
    "How does the LoRA training pipeline work?",
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
  currentDeepSearchCompare,
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

  // Phase 1C (2026-05-23) — pending action awaiting user confirmation.
  // The dispatcher fails closed on confirm-mode actions when no
  // requestConfirmation hook is provided; this state + the resolver
  // ref are how the modal proxies the user's choice back to it.
  const [pendingAction, setPendingAction] = useState<ChatActionSpec | null>(null);
  const confirmResolverRef = useRef<((confirmed: boolean) => void) | null>(null);

  const requestConfirmation = useCallback(
    (action: ChatActionSpec): Promise<boolean> => {
      return new Promise((resolve) => {
        confirmResolverRef.current = resolve;
        setPendingAction(action);
      });
    },
    [],
  );

  const handleActionClick = useCallback(
    async (action: ChatActionSpec) => {
      const result = await dispatchChatAction(action, { requestConfirmation });
      if (result.status === "error" && result.quotaExceeded) {
        // Surface the quota-exceeded message inline. The user can also
        // click the visible Upgrade CTA in /dashboard/subscription.
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `${result.message} Visit /dashboard/subscription to upgrade.`,
            mode: "quota_notice",
          },
        ]);
      } else if (result.status === "error") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Could not complete that action: ${result.message}`,
            mode: "action_error",
          },
        ]);
      }
    },
    [requestConfirmation],
  );

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

  useEffect(() => {
    if (typeof window === "undefined") return;

    const onPrefill = (event: Event) => {
      const customEvent = event as CustomEvent<{ prompt?: string }>;
      const prompt = customEvent?.detail?.prompt;
      if (!prompt || typeof prompt !== "string") return;

      setIsExpanded(true);
      setInput(prompt);
      setTimeout(() => inputRef.current?.focus(), 100);
    };

    window.addEventListener("climatenews:assistant-prefill", onPrefill);
    return () => window.removeEventListener("climatenews:assistant-prefill", onPrefill);
  }, []);

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
    if (currentPage === "research" || currentPage === "deep-search") return "research_analysis";
    return "general";
  };

  const mode = determineMode();
  const modeInfo = MODE_LABELS[mode] || MODE_LABELS.general;
  const ModeIcon = modeInfo.icon;

  const contextSummary = useMemo(() => {
    if (contextLabel) return contextLabel;

    const parts: string[] = [];
    if (currentPage && currentPage !== "default") parts.push(`/${currentPage}`);
    if (currentCountry) parts.push(`country ${currentCountry}`);
    if (currentArticleId) parts.push("article view");
    if (currentAnalysisId) parts.push("URL analysis");
    if (currentDeepSearchCompare?.query_a && currentDeepSearchCompare?.query_b) {
      parts.push("deep-search compare");
    } else if (currentDeepSearchQuery) {
      parts.push("deep-search result");
    }
    if (currentSourceId) parts.push(`source ${currentSourceId}`);

    return parts.length > 0 ? parts.join(" • ") : "Global platform context";
  }, [
    contextLabel,
    currentPage,
    currentCountry,
    currentArticleId,
    currentAnalysisId,
    currentDeepSearchCompare,
    currentDeepSearchQuery,
    currentSourceId,
  ]);

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
      if (currentDeepSearchCompare) viewContext.deep_search_compare = currentDeepSearchCompare;
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

      if (!res.ok) {
        // Phase 9 (2026-05-25) — surface backend error detail so users
        // can act on it instead of seeing a generic "couldn't process".
        let detail = "";
        try {
          const errBody = await res.json();
          detail =
            errBody?.detail?.message ||
            (typeof errBody?.detail === "string" ? errBody.detail : "") ||
            errBody?.message ||
            "";
        } catch {
          /* ignore body parsing */
        }
        const friendlyDetail = detail
          ? ` (${detail.slice(0, 200)})`
          : "";
        throw new Error(`Chat backend returned ${res.status}${friendlyDetail}`);
      }
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

      if (Array.isArray(data.actions) && data.actions.length > 0) {
        assistantMessage.actions = data.actions
          .filter((a: any) => a && a.type && a.label)
          .slice(0, 3) as ChatActionSpec[];
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
    } catch (err) {
      // Show what actually failed so the user (and ops) can act.
      const message =
        err instanceof Error && err.message
          ? err.message
          : "Network error reaching the chat service.";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `I hit a snag answering that — ${message}. Try rephrasing, or refresh and try again.`,
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

          <div className="px-4 py-2 border-b border-slate-700/40 bg-slate-900/70">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Current context</p>
            <p className="text-[11px] text-slate-300 truncate" title={contextSummary}>
              {contextSummary}
            </p>
          </div>

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[120px] max-h-[340px] scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {messages.length === 0 && (
              <div className="py-3">
                {/* Page context help */}
                <div className="mb-3 px-3 py-2.5 bg-slate-800/80 border border-teal-500/20 rounded-lg">
                  <div className="text-xs text-slate-300 leading-relaxed">
                    <Markdown
                      content={PAGE_HELP[currentPage] || PAGE_HELP.default}
                      className="text-slate-300 [&_p]:text-slate-300 [&_strong]:text-teal-400 [&_p]:text-xs [&_p]:leading-relaxed"
                    />
                  </div>
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
                  <button
                    onClick={() => handleExampleClick("What context are you currently using for my question?")}
                    className="text-[11px] px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-full border border-slate-700/50 hover:border-teal-500/40 transition-all"
                  >
                    Show current context
                  </button>
                  <button
                    onClick={() => handleExampleClick("How should I phrase my question on this page for the strongest analysis?")}
                    className="text-[11px] px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-full border border-slate-700/50 hover:border-teal-500/40 transition-all"
                  >
                    Help me ask better
                  </button>
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
                    <>
                      <Markdown content={msg.content} className="text-slate-200 [&_p]:text-slate-200 [&_strong]:text-white [&_a]:text-teal-400" />
                      <div className="mt-2">
                        <AIProvenanceBadge
                          provenance={{
                            model: "deepseek-chat",
                            prompt_name: "chat_synthesis_with_actions",
                            prompt_version: "v1.0",
                            retrieval_strategy: "hybrid_rag",
                            timestamp: new Date().toISOString(),
                          }}
                        />
                      </div>
                      {msg.actions && msg.actions.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5" data-testid="chat-actions-row">
                          {msg.actions.map((a, i) => {
                            const requiresConfirm = ACTION_MODES[a.type] === "confirm";
                            return (
                              <button
                                key={i}
                                type="button"
                                onClick={() => handleActionClick(a)}
                                className={`px-2.5 py-1 text-xs rounded-full border transition-colors cursor-pointer ${
                                  requiresConfirm
                                    ? "bg-amber-600/20 hover:bg-amber-600/40 text-amber-200 border-amber-500/40"
                                    : "bg-teal-600/20 hover:bg-teal-600/40 text-teal-300 border-teal-500/30"
                                }`}
                                aria-label={
                                  requiresConfirm
                                    ? `${a.label} (requires confirmation)`
                                    : a.label
                                }
                                title={
                                  requiresConfirm
                                    ? "Will ask for confirmation before running"
                                    : undefined
                                }
                                data-action-type={a.type}
                                data-action-mode={ACTION_MODES[a.type]}
                              >
                                {a.label}
                                {requiresConfirm && (
                                  <span className="ml-1 opacity-70" aria-hidden="true">⚠</span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </>
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
        data-chat-toggle
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

      {/* Phase 1C (2026-05-23) — confirmation modal for destructive /
          quota-consuming chat actions. Pending action → user choice via
          this modal → dispatcher resolves and runs (or skips) the side
          effect. AUTO-mode actions never open this. */}
      <ChatActionConfirmModal
        action={pendingAction}
        onConfirm={() => {
          confirmResolverRef.current?.(true);
          confirmResolverRef.current = null;
          setPendingAction(null);
        }}
        onCancel={() => {
          confirmResolverRef.current?.(false);
          confirmResolverRef.current = null;
          setPendingAction(null);
        }}
      />
    </div>
  );
}
