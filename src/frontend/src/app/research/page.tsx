"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  Link2,
  Upload,
  Loader2,
  CheckCircle,
  AlertTriangle,
  BookOpen,
  BarChart3,
  Activity,
  MessageCircle,
  ChevronDown,
  ChevronUp,
  LogIn,
} from "lucide-react";
import ResearchFeedPanel from "@/components/ResearchFeedPanel";
import DefaultTopicsBrowser from "@/components/DefaultTopicsBrowser";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface AnalysisResult {
  status: string;
  report_id?: string;
  document: {
    title: string;
    content_type: string;
    doi?: string;
    venue?: string;
    authors: string[];
    published_date?: string;
    word_count: number;
    reference_count?: number;
  };
  analysis: {
    summary: string;
    key_claims: string[];
    methodology_score: number;
    citation_score: number;
    data_transparency_score: number;
    topics: string[];
    climate_relevance: string;
    limitations_noted: boolean;
    peer_reviewed_indicators: boolean;
    potential_biases: string[];
    recommendation: string;
    methodology_detected?: boolean;
    data_indicators?: Record<string, boolean>;
  };
  credibility: {
    prior_score: number;
    posterior: { posterior_score: number; confidence_interval: number[]; evidence_count: number };
    has_doi: boolean;
    venue_recognized: boolean;
  };
}

function extractErrorMessage(payload: any, fallback: string): string {
  // Golden #2 fix (2026-05-27): /research/upload now returns structured
  // 403 detail objects with {error, message, upgrade_url}; the old code
  // did `new Error(data.detail || ...)` which coerced the object to
  // "[object Object]". Pull the human-readable field out cleanly.
  if (!payload) return fallback;
  const d = payload.detail ?? payload;
  if (typeof d === "string") return d;
  if (typeof d === "object" && d !== null) {
    if (typeof d.message === "string") return d.message;
    if (typeof d.detail === "string") return d.detail;
    if (typeof d.error === "string") return d.error;
  }
  return fallback;
}

function hasAuthToken(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("clilens_token");
}

export default function ResearchPage() {
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [inputMode, setInputMode] = useState<"url" | "doi" | "text" | "upload">("url");
  const [url, setUrl] = useState("");
  const [doi, setDoi] = useState("");
  const [text, setText] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedRefreshKey, setFeedRefreshKey] = useState(0);

  const openAssistant = (prompt?: string) => {
    if (typeof window !== "undefined" && prompt) {
      window.dispatchEvent(
        new CustomEvent("climatenews:assistant-prefill", {
          detail: { prompt },
        }),
      );
    }
    const assistant = document.querySelector<HTMLElement>("[data-chat-toggle]");
    assistant?.click();
  };

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const token = localStorage.getItem("clilens_token");

      let resp: Response;
      if (inputMode === "upload") {
        if (!uploadFile) throw new Error("Pick a file to upload");
        if (!token) {
          throw new Error(
            "File upload requires sign-in (Standard+ tier). Use 'Paste text' mode if you don't want to sign in.",
          );
        }
        const form = new FormData();
        form.append("file", uploadFile);
        const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
        resp = await fetch(`${API_URL}/api/research/upload`, {
          method: "POST",
          headers,
          body: form,
        });
      } else {
        const body: Record<string, string> = {};
        if (inputMode === "url") body.url = url;
        else if (inputMode === "doi") body.doi = doi;
        else body.text = text;
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;
        resp = await fetch(`${API_URL}/api/research/analyze`, {
          method: "POST",
          headers,
          body: JSON.stringify(body),
        });
      }
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(
          extractErrorMessage(data, `Analysis failed (HTTP ${resp.status})`),
        );
      }
      setResult(await resp.json());
    } catch (err: any) {
      setError(err?.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  const sc = (s: number) =>
    s >= 80 ? "text-green-600" : s >= 60 ? "text-yellow-600" : s >= 40 ? "text-orange-500" : "text-red-600";
  const sb = (s: number) =>
    s >= 80 ? "bg-green-100" : s >= 60 ? "bg-yellow-100" : s >= 40 ? "bg-orange-100" : "bg-red-100";

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <BookOpen className="h-5 w-5 text-teal-600" />
            <h1 className="text-xl font-bold text-gray-900">Research Feed</h1>
          </div>
          <p className="mt-2 text-sm text-gray-500 ml-9">
            Peer-reviewed climate research delivered daily via CrossRef — plus on-demand analysis of any paper, report, or PDF.
          </p>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {/* 1 — Default topics browser: PRIMARY surface */}
        <section className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <DefaultTopicsBrowser
            onSubscribed={() => setFeedRefreshKey((k) => k + 1)}
          />
        </section>

        {/* 2 — User's subscriptions + feed cards (feed style) */}
        <section>
          <ResearchFeedPanel key={feedRefreshKey} />
        </section>

        {/* 3 — Analyze a specific document (collapsible secondary) */}
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <button
            type="button"
            onClick={() => setAnalyzeOpen((o) => !o)}
            className="w-full flex items-center justify-between p-5 hover:bg-gray-50 transition-colors text-left"
            aria-expanded={analyzeOpen}
          >
            <div className="flex items-center gap-2.5">
              <BarChart3 className="h-5 w-5 text-teal-600" />
              <div>
                <h2 className="text-base font-semibold text-gray-900">
                  Analyze a specific paper or report
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Drop a URL, DOI, paste text, or upload a PDF / Word document for full
                  credibility + methodology analysis.
                </p>
              </div>
            </div>
            {analyzeOpen ? (
              <ChevronUp className="h-5 w-5 text-gray-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-gray-400" />
            )}
          </button>

          {analyzeOpen && (
            <div className="p-6 pt-0 border-t border-gray-100">
              <div className="flex flex-wrap gap-2 my-4">
                {(["url", "doi", "text", "upload"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setInputMode(m)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      inputMode === m
                        ? "bg-teal-600 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {m === "url" && (
                      <span className="flex items-center gap-1.5">
                        <Link2 className="h-4 w-4" /> URL
                      </span>
                    )}
                    {m === "doi" && (
                      <span className="flex items-center gap-1.5">
                        <FileText className="h-4 w-4" /> DOI
                      </span>
                    )}
                    {m === "text" && (
                      <span className="flex items-center gap-1.5">
                        <FileText className="h-4 w-4" /> Paste text
                      </span>
                    )}
                    {m === "upload" && (
                      <span className="flex items-center gap-1.5">
                        <Upload className="h-4 w-4" /> Upload PDF/Word
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {inputMode === "url" && (
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/report.pdf"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                />
              )}
              {inputMode === "doi" && (
                <input
                  type="text"
                  value={doi}
                  onChange={(e) => setDoi(e.target.value)}
                  placeholder="10.1038/s41586-021-03984-4"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                />
              )}
              {inputMode === "text" && (
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste the research report text here..."
                  rows={8}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none resize-y"
                />
              )}
              {inputMode === "upload" && (
                <div className="space-y-2">
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.md,.html"
                    onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100"
                  />
                  {uploadFile && (
                    <p className="text-xs text-gray-600">
                      Selected: {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                  {!hasAuthToken() && (
                    <div className="flex items-start gap-2 p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                      <LogIn className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                      <span>
                        File upload requires sign-in (Standard+ tier).{" "}
                        <Link href="/login" className="font-medium underline">
                          Sign in
                        </Link>{" "}
                        — or use "Paste text" for anonymous analysis.
                      </span>
                    </div>
                  )}
                  <p className="text-xs text-gray-500">
                    Up to 25 MiB. PDF, Word (.docx/.doc), TXT, Markdown, HTML.
                    Sustainability reports + theses + working papers all welcome.
                  </p>
                </div>
              )}

              {error && (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <button
                type="button"
                onClick={handleAnalyze}
                disabled={loading || (!url && !doi && !text && !uploadFile)}
                className="mt-4 w-full py-3 bg-teal-600 text-white rounded-lg font-medium hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" /> Analyzing...
                  </>
                ) : (
                  <>
                    <BarChart3 className="h-5 w-5" /> Analyze Report
                  </>
                )}
              </button>

              <div className="mt-3 flex items-center justify-end">
                <button
                  type="button"
                  onClick={() =>
                    openAssistant(
                      "Help me choose the best analysis mode (URL / DOI / text) and explain what evidence quality signals I should look for.",
                    )
                  }
                  className="text-xs text-teal-700 hover:text-teal-900 flex items-center gap-1.5"
                >
                  <MessageCircle className="h-3.5 w-3.5" />
                  Get help with analysis inputs
                </button>
              </div>
            </div>
          )}
        </section>

        {result && result.status === "completed" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <h2 className="text-lg font-bold text-gray-900 mb-3">
                {result.document.title || "Untitled Document"}
              </h2>
              <div className="flex flex-wrap gap-3 text-sm text-gray-500">
                {result.document.authors.length > 0 && (
                  <span>{result.document.authors.slice(0, 3).join(", ")}</span>
                )}
                {result.document.venue && (
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded">
                    {result.document.venue}
                  </span>
                )}
                {result.document.doi && (
                  <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded">
                    DOI: {result.document.doi}
                  </span>
                )}
                <span>{result.document.word_count.toLocaleString()} words</span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[
                {
                  label: "Overall Score",
                  value: result.credibility.posterior.posterior_score,
                  sub: `CI: [${result.credibility.posterior.confidence_interval[0]} - ${result.credibility.posterior.confidence_interval[1]}]`,
                },
                { label: "Methodology", value: result.analysis.methodology_score },
                { label: "Citations", value: result.analysis.citation_score },
                { label: "Data Transparency", value: result.analysis.data_transparency_score },
              ].map((item) => (
                <div key={item.label} className={`rounded-xl p-5 ${sb(item.value)}`}>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-1">{item.label}</p>
                  <p className={`text-3xl font-bold ${sc(item.value)}`}>{item.value}</p>
                  {item.sub && <p className="text-xs text-gray-500 mt-1">{item.sub}</p>}
                </div>
              ))}
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Activity className="h-4 w-4 text-teal-600" />
                Scientific Rigor Indicators
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-center">
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-lg font-bold text-gray-900">
                    {result.document.reference_count ?? 0}
                  </p>
                  <p className="text-[11px] text-gray-500">References detected</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p
                    className={`text-lg font-bold ${
                      result.analysis.methodology_detected ? "text-green-600" : "text-gray-500"
                    }`}
                  >
                    {result.analysis.methodology_detected ? "Yes" : "No"}
                  </p>
                  <p className="text-[11px] text-gray-500">Methodology section</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p
                    className={`text-lg font-bold ${
                      result.analysis.peer_reviewed_indicators ? "text-green-600" : "text-amber-600"
                    }`}
                  >
                    {result.analysis.peer_reviewed_indicators ? "Likely" : "Unclear"}
                  </p>
                  <p className="text-[11px] text-gray-500">Peer-review signals</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-lg font-bold text-gray-900">
                    {result.credibility.posterior.evidence_count}
                  </p>
                  <p className="text-[11px] text-gray-500">Evidence factors used</p>
                </div>
              </div>

              {result.analysis.data_indicators && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {Object.entries(result.analysis.data_indicators).map(([k, v]) => (
                    <span
                      key={k}
                      className={`px-2 py-1 rounded-full text-[11px] border ${
                        v
                          ? "bg-green-50 text-green-700 border-green-200"
                          : "bg-gray-50 text-gray-500 border-gray-200"
                      }`}
                    >
                      {k.replace("has_", "").replace(/_/g, " ")}: {v ? "yes" : "no"}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Key Claims</h3>
              <ul className="space-y-2">
                {result.analysis.key_claims.map((claim, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                    <CheckCircle className="h-4 w-4 text-teal-500 flex-shrink-0 mt-0.5" />
                    <span>{claim}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">Summary</h3>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                {result.analysis.summary}
              </p>
            </div>

            {result.analysis.potential_biases.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-amber-900 mb-2 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  Potential Biases
                </h3>
                <ul className="space-y-1 text-sm text-amber-800">
                  {result.analysis.potential_biases.map((bias, idx) => (
                    <li key={idx}>• {bias}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
