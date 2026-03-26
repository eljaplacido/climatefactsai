"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircle, X, Send, Sparkles, Loader2, MapPin, BookOpen, Search, ChevronDown, ChevronUp } from "lucide-react";
import Markdown from "./Markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
  highlighted_countries?: string[];
  cited_articles?: { article_id: string; title: string }[];
  mode?: string;
}

interface AgenticAssistantProps {
  currentPage?: string;
  currentArticleId?: string;
  currentCountry?: string;
  onHighlightCountries?: (countries: string[]) => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const EXAMPLE_QUERIES: Record<string, string[]> = {
  map: [
    "What are the biggest climate risks in Southeast Asia?",
    "Compare renewable energy progress: Europe vs Asia",
    "Show me countries with rising temperature anomalies",
    "Which African nations have the most climate coverage?",
  ],
  articles: [
    "How does this compare to other findings on this topic?",
    "What are the key scientific claims in this article?",
    "Is this source reliable for climate reporting?",
  ],
  default: [
    "What are the latest climate trends globally?",
    "Summarize recent Arctic ice coverage reports",
    "Which policies are most effective at reducing emissions?",
    "Find contradictory claims about carbon capture",
  ],
};

export default function AgenticAssistant({
  currentPage = "default",
  currentArticleId,
  currentCountry,
  onHighlightCountries,
}: AgenticAssistantProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const determineMode = (): string => {
    if (currentPage === "map") return "map_intelligence";
    if (currentArticleId) return "article_qa";
    if (currentPage === "research") return "research_analysis";
    return "general";
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const mode = determineMode();
      const token = typeof window !== "undefined" ? localStorage.getItem("clilens_token") : null;

      let endpoint = `${API_BASE}/api/chat`;
      let body: Record<string, any> = {
        question: userMessage.content,
        mode,
        session_id: sessionId,
      };

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
      } else if (mode === "article_qa" && currentArticleId) {
        endpoint = `${API_BASE}/api/articles/${currentArticleId}/ask`;
        body = {
          question: userMessage.content,
          conversation_context: messages.slice(-4).map((m) => ({
            role: m.role,
            content: m.content,
          })),
        };
      }

      const headers: Record<string, string> = { "Content-Type": "application/json" };
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
        content: data.answer || data.response || data.text || "No response generated.",
        mode,
      };

      if (data.highlighted_countries) {
        assistantMessage.highlighted_countries = data.highlighted_countries;
        onHighlightCountries?.(data.highlighted_countries);
      }

      if (data.country_highlights) {
        assistantMessage.highlighted_countries = data.country_highlights.map(
          (h: any) => h.country_code
        );
        onHighlightCountries?.(assistantMessage.highlighted_countries || []);
      }

      if (data.sources || data.citations) {
        assistantMessage.cited_articles = (data.sources || data.citations || [])
          .filter((s: any) => s.article_id)
          .slice(0, 5)
          .map((s: any) => ({ article_id: s.article_id, title: s.title || s.source_name }));
      }

      if (data.session_id) setSessionId(data.session_id);

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
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

  const examples = EXAMPLE_QUERIES[currentPage] || EXAMPLE_QUERIES.default;

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 bg-teal-600 text-white rounded-full shadow-lg hover:bg-teal-700 transition-all hover:scale-105"
      >
        <Sparkles className="h-5 w-5" />
        <span className="text-sm font-medium">Ask Climate AI</span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-96 max-h-[600px] bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-teal-600 to-teal-700 text-white">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          <span className="font-semibold text-sm">Climate Intelligence Assistant</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setIsMinimized(!isMinimized)} className="p-1 hover:bg-white/20 rounded">
            {isMinimized ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          <button onClick={() => setIsOpen(false)} className="p-1 hover:bg-white/20 rounded">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Context indicator */}
          <div className="px-4 py-2 bg-gray-50 border-b text-xs text-gray-500 flex items-center gap-2">
            {currentPage === "map" && <><MapPin className="h-3 w-3" /> Map Intelligence Mode</>}
            {currentArticleId && <><BookOpen className="h-3 w-3" /> Article Analysis Mode</>}
            {currentPage === "research" && <><Search className="h-3 w-3" /> Research Mode</>}
            {!currentArticleId && currentPage !== "map" && currentPage !== "research" && (
              <><MessageCircle className="h-3 w-3" /> General Climate Q&A</>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[200px] max-h-[360px]">
            {messages.length === 0 && (
              <div className="text-center py-6">
                <Sparkles className="h-8 w-8 text-teal-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500 mb-4">Ask me about climate news, data, or trends</p>
                <div className="space-y-2">
                  {examples.slice(0, 3).map((q) => (
                    <button
                      key={q}
                      onClick={() => { setInput(q); inputRef.current?.focus(); }}
                      className="block w-full text-left text-xs px-3 py-2 bg-gray-50 hover:bg-teal-50 rounded-lg border border-gray-200 hover:border-teal-300 transition text-gray-600"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-teal-600 text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {msg.role === "assistant" ? <Markdown content={msg.content} /> : msg.content}
                  {msg.cited_articles && msg.cited_articles.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                      {msg.cited_articles.map((a) => (
                        <a
                          key={a.article_id}
                          href={`/articles/${a.article_id}`}
                          className="block text-xs text-teal-600 hover:underline truncate"
                        >
                          {a.title}
                        </a>
                      ))}
                    </div>
                  )}
                  {msg.highlighted_countries && msg.highlighted_countries.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {msg.highlighted_countries.slice(0, 5).map((cc) => (
                        <span key={cc} className="inline-block px-1.5 py-0.5 bg-teal-100 text-teal-700 text-[10px] rounded">
                          {cc}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg px-3 py-2 flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-teal-600" />
                  <span className="text-sm text-gray-500">Analyzing...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-4 py-3 border-t bg-white">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask about climate news, data, or trends..."
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="p-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
