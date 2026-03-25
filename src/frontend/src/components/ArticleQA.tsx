"use client";

import { useState, useRef, useEffect } from "react";
import { MessageCircle, Send, Loader2, ChevronDown, ChevronUp, AlertCircle, Search, ArrowRight } from "lucide-react";
import type { ConversationEntry, ClaimDetail } from "@/types";
import { api } from "@/lib/api";
import Markdown from "./Markdown";

interface ArticleQAProps {
  articleId: string;
  articleTitle?: string;
  contentCategory?: string;
  claims?: ClaimDetail[];
}

// Category-specific suggested questions
const CATEGORY_QUESTIONS: Record<string, string[]> = {
  climate_science: [
    "What scientific evidence supports the key claims?",
    "How does this align with IPCC findings?",
    "What are the uncertainty ranges mentioned?",
  ],
  policy: [
    "Which stakeholders are most affected?",
    "What regulations are referenced?",
    "What are the implementation challenges?",
  ],
  sustainability: [
    "How are sustainability claims measured?",
    "Which SDGs does this relate to?",
    "Are there greenwashing concerns?",
  ],
  circular_economy: [
    "What material flows are discussed?",
    "How scalable is this approach?",
    "What are the economic implications?",
  ],
  green_transition: [
    "What is the transition timeline?",
    "How mature is the technology discussed?",
    "What investment is required?",
  ],
  localized_forecast: [
    "How does this compare to historical patterns?",
    "What data sources confirm the forecast?",
    "Is this weather or a climate trend?",
  ],
};

const DEFAULT_QUESTIONS = [
  "What are the main claims in this article?",
  "How reliable are the sources cited?",
  "What evidence supports the key findings?",
];

function getFollowUpSuggestions(lastAnswer: string, claims?: ClaimDetail[]): string[] {
  const suggestions: string[] = [];

  // Generate follow-ups based on answer content
  if (lastAnswer.toLowerCase().includes("disputed") || lastAnswer.toLowerCase().includes("unverified")) {
    suggestions.push("Why are some claims disputed?");
  }
  if (lastAnswer.toLowerCase().includes("evidence") || lastAnswer.toLowerCase().includes("source")) {
    suggestions.push("Can you detail the evidence chain?");
  }
  if (lastAnswer.toLowerCase().includes("confidence")) {
    suggestions.push("What factors affect the confidence score?");
  }

  // Add a claim-specific question if claims are available
  if (claims && claims.length > 0) {
    const disputed = claims.find(
      (c) => c.fact_check?.verification_status === "disputed"
    );
    if (disputed) {
      suggestions.push(`Why is "${disputed.claim_text.slice(0, 50)}..." disputed?`);
    }
  }

  // Always offer a deep-dive option
  if (suggestions.length === 0) {
    suggestions.push("What should I watch for in future coverage?");
    suggestions.push("How does this compare to other countries?");
  }

  return suggestions.slice(0, 3);
}

export default function ArticleQA({ articleId, articleTitle, contentCategory, claims }: ArticleQAProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [question, setQuestion] = useState("");
  const [conversations, setConversations] = useState<ConversationEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [followUpSuggestions, setFollowUpSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isExpanded && !historyLoaded) {
      loadHistory();
    }
  }, [isExpanded]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversations]);

  async function loadHistory() {
    try {
      const history = await api.getArticleConversations(articleId, 10);
      if (history && history.entries) {
        setConversations([...history.entries].reverse());
      }
      setHistoryLoaded(true);
    } catch {
      setHistoryLoaded(true);
    }
  }

  async function handleAsk(q?: string) {
    const queryText = (q || question).trim();
    if (!queryText || isLoading) return;
    setQuestion("");
    setError(null);
    setIsLoading(true);
    setFollowUpSuggestions([]);

    const tempEntry: ConversationEntry = {
      conversation_id: "pending",
      question: queryText,
      answer: "",
      confidence: 0,
      context_used: [],
    };
    setConversations((prev) => [...prev, tempEntry]);

    try {
      const result = await api.askArticleQuestion(articleId, queryText);
      setConversations((prev) =>
        prev.map((c) =>
          c.conversation_id === "pending"
            ? { ...result, question: queryText }
            : c
        )
      );
      if (result.error) {
        setError(
          result.error === "rate_limit"
            ? "Daily question limit reached. Upgrade for more."
            : result.answer
        );
      } else {
        // Generate follow-up suggestions based on the answer
        setFollowUpSuggestions(getFollowUpSuggestions(result.answer, claims));
      }
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to get answer. Please try again.";
      setConversations((prev) =>
        prev.filter((c) => c.conversation_id !== "pending")
      );
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  }

  // Pick suggested questions based on category
  const suggestedQuestions =
    (contentCategory && CATEGORY_QUESTIONS[contentCategory]) || DEFAULT_QUESTIONS;

  return (
    <section className="border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-5 py-4 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2 text-gray-700">
          <MessageCircle className="h-5 w-5 text-clilens-primary" />
          <span className="font-semibold text-sm">Ask about this article</span>
          {conversations.length > 0 && (
            <span className="text-xs bg-clilens-primary/10 text-clilens-primary px-2 py-0.5 rounded-full">
              {conversations.length}
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        )}
      </button>

      {isExpanded && (
        <div className="p-5 space-y-4">
          {/* Conversation history */}
          {conversations.length > 0 && (
            <div className="max-h-96 overflow-y-auto space-y-3 pr-1">
              {conversations.map((entry, idx) => (
                <div key={entry.conversation_id || idx} className="space-y-2">
                  {/* User question */}
                  <div className="flex justify-end">
                    <div className="max-w-[80%] bg-clilens-primary text-white rounded-xl rounded-br-sm px-4 py-2 text-sm">
                      {entry.question}
                    </div>
                  </div>
                  {/* AI answer with markdown rendering */}
                  {entry.answer ? (
                    <div className="flex justify-start">
                      <div className="max-w-[80%] bg-gray-100 rounded-xl rounded-bl-sm px-4 py-2 text-sm text-gray-800">
                        <div className="prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2">
                          <Markdown content={entry.answer} />
                        </div>
                        {entry.confidence > 0 && (
                          <p className="mt-1 text-[10px] text-gray-400">
                            Confidence: {Math.round(entry.confidence * 100)}%
                          </p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 rounded-xl px-4 py-2">
                        <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Suggested questions (initial state) */}
          {conversations.length === 0 && !isLoading && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500">Suggested questions:</p>
              <div className="flex flex-wrap gap-2">
                {suggestedQuestions.map((sq) => (
                  <button
                    key={sq}
                    onClick={() => handleAsk(sq)}
                    className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-3 py-1.5 rounded-full transition-colors"
                  >
                    {sq}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Follow-up suggestions (after an answer) */}
          {followUpSuggestions.length > 0 && !isLoading && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500">Follow up:</p>
              <div className="flex flex-wrap gap-2">
                {followUpSuggestions.map((sq) => (
                  <button
                    key={sq}
                    onClick={() => handleAsk(sq)}
                    className="inline-flex items-center gap-1 text-xs bg-clilens-primary/5 hover:bg-clilens-primary/10 text-clilens-primary border border-clilens-primary/20 px-3 py-1.5 rounded-full transition-colors"
                  >
                    <ArrowRight className="h-3 w-3" />
                    {sq}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Deep-dive buttons */}
          {conversations.length > 0 && !isLoading && (
            <div className="flex gap-2">
              <button
                onClick={() => handleAsk("Give me a deep dive on the most significant claim")}
                className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-clilens-primary border border-gray-200 hover:border-clilens-primary/30 px-3 py-1.5 rounded-lg transition-colors"
              >
                <Search className="h-3 w-3" />
                Deep dive
              </button>
              {claims && claims.length > 0 && (
                <button
                  onClick={() => handleAsk("Find similar articles covering these claims")}
                  className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-clilens-primary border border-gray-200 hover:border-clilens-primary/30 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Search className="h-3 w-3" />
                  Find similar articles
                </button>
              )}
            </div>
          )}

          {/* Error display */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Input */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about this article..."
              className="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-clilens-primary focus:border-transparent outline-none"
              disabled={isLoading}
              maxLength={500}
            />
            <button
              onClick={() => handleAsk()}
              disabled={!question.trim() || isLoading}
              className="p-2.5 bg-clilens-primary text-white rounded-lg disabled:opacity-50 hover:bg-clilens-primary/90 transition-colors"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
