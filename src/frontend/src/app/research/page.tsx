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
  Shield,
  MessageCircle,
  Activity,
} from "lucide-react";

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
  credibility: { prior_score: number; posterior: { posterior_score: number; confidence_interval: number[]; evidence_count: number }; has_doi: boolean; venue_recognized: boolean };
}

export default function ResearchPage() {
  const [inputMode, setInputMode] = useState<"url" | "doi" | "text">("url");
  const [url, setUrl] = useState("");
  const [doi, setDoi] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openAssistant = (prompt?: string) => {
    if (typeof window !== "undefined" && prompt) {
      window.dispatchEvent(
        new CustomEvent("climatenews:assistant-prefill", {
          detail: { prompt },
        })
      );
    }
    const assistant = document.querySelector<HTMLElement>("[data-chat-toggle]");
    assistant?.click();
  };

  async function handleAnalyze() {
    setLoading(true); setError(null); setResult(null);
    try {
      const body: Record<string, string> = {};
      if (inputMode === "url") body.url = url;
      else if (inputMode === "doi") body.doi = doi;
      else body.text = text;
      const token = localStorage.getItem("clilens_token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const resp = await fetch(`${API_URL}/api/research/analyze`, { method: "POST", headers, body: JSON.stringify(body) });
      if (!resp.ok) { const data = await resp.json(); throw new Error(data.detail || "Analysis failed"); }
      setResult(await resp.json());
    } catch (err: any) { setError(err.message || "Analysis failed"); }
    finally { setLoading(false); }
  }

  const sc = (s: number) => s >= 80 ? "text-green-600" : s >= 60 ? "text-yellow-600" : s >= 40 ? "text-orange-500" : "text-red-600";
  const sb = (s: number) => s >= 80 ? "bg-green-100" : s >= 60 ? "bg-yellow-100" : s >= 40 ? "bg-orange-100" : "bg-red-100";

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700"><ArrowLeft className="h-5 w-5" /></Link>
            <BookOpen className="h-5 w-5 text-teal-600" />
            <h1 className="text-xl font-bold text-gray-900">Research Report Analysis</h1>
          </div>
          <p className="mt-2 text-sm text-gray-500 ml-9">Analyze academic papers, industry reports, and policy documents for climate claim credibility</p>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex gap-2 mb-4">
            {(["url", "doi", "text"] as const).map((m) => (
              <button key={m} onClick={() => setInputMode(m)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${inputMode === m ? "bg-teal-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
                {m === "url" && <span className="flex items-center gap-1.5"><Link2 className="h-4 w-4" /> URL</span>}
                {m === "doi" && <span className="flex items-center gap-1.5"><FileText className="h-4 w-4" /> DOI</span>}
                {m === "text" && <span className="flex items-center gap-1.5"><Upload className="h-4 w-4" /> Paste text</span>}
              </button>
            ))}
          </div>
          {inputMode === "url" && <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/report.pdf" className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none" />}
          {inputMode === "doi" && <input type="text" value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="10.1038/s41586-021-03984-4" className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none" />}
          {inputMode === "text" && <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the research report text here..." rows={8} className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none resize-y" />}
          {error && <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>}
          <button onClick={handleAnalyze} disabled={loading || (!url && !doi && !text)}
            className="mt-4 w-full py-3 bg-teal-600 text-white rounded-lg font-medium hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
            {loading ? <><Loader2 className="h-5 w-5 animate-spin" /> Analyzing...</> : <><BarChart3 className="h-5 w-5" /> Analyze Report</>}
          </button>

          <div className="mt-3 flex items-center justify-end">
            <button
              type="button"
              onClick={() => openAssistant("Help me choose the best analysis mode (URL / DOI / text) and explain what evidence quality signals I should look for.")}
              className="text-xs text-teal-700 hover:text-teal-900 flex items-center gap-1.5"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              Get help with analysis inputs
            </button>
          </div>
        </div>

        {result && result.status === "completed" && (
          <div className="mt-8 space-y-6">
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <h2 className="text-lg font-bold text-gray-900 mb-3">{result.document.title || "Untitled Document"}</h2>
              <div className="flex flex-wrap gap-3 text-sm text-gray-500">
                {result.document.authors.length > 0 && <span>{result.document.authors.slice(0, 3).join(", ")}</span>}
                {result.document.venue && <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded">{result.document.venue}</span>}
                {result.document.doi && <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded">DOI: {result.document.doi}</span>}
                <span>{result.document.word_count.toLocaleString()} words</span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[
                { label: "Overall Score", value: result.credibility.posterior.posterior_score, sub: `CI: [${result.credibility.posterior.confidence_interval[0]} - ${result.credibility.posterior.confidence_interval[1]}]` },
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
                  <p className="text-lg font-bold text-gray-900">{result.document.reference_count ?? 0}</p>
                  <p className="text-[11px] text-gray-500">References detected</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className={`text-lg font-bold ${result.analysis.methodology_detected ? "text-green-600" : "text-gray-500"}`}>
                    {result.analysis.methodology_detected ? "Yes" : "No"}
                  </p>
                  <p className="text-[11px] text-gray-500">Methodology section</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className={`text-lg font-bold ${result.analysis.peer_reviewed_indicators ? "text-green-600" : "text-amber-600"}`}>
                    {result.analysis.peer_reviewed_indicators ? "Likely" : "Unclear"}
                  </p>
                  <p className="text-[11px] text-gray-500">Peer-review signals</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-lg font-bold text-gray-900">{result.credibility.posterior.evidence_count}</p>
                  <p className="text-[11px] text-gray-500">Evidence factors used</p>
                </div>
              </div>

              {result.analysis.data_indicators && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {Object.entries(result.analysis.data_indicators).map(([k, v]) => (
                    <span
                      key={k}
                      className={`px-2 py-1 rounded-full text-[11px] border ${v ? "bg-green-50 text-green-700 border-green-200" : "bg-gray-50 text-gray-500 border-gray-200"}`}
                    >
                      {k.replace("has_", "").replace(/_/g, " ")}: {v ? "yes" : "no"}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <h3 className="font-semibold text-gray-900 mb-3">Summary</h3>
              <p className="text-sm text-gray-700 leading-relaxed">{result.analysis.summary}</p>
              {result.analysis.key_claims.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Key Claims</h4>
                  <ul className="space-y-1">{result.analysis.key_claims.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600"><CheckCircle className="h-4 w-4 text-teal-500 mt-0.5 flex-shrink-0" />{c}</li>
                  ))}</ul>
                </div>
              )}
              {result.analysis.potential_biases.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Potential Biases</h4>
                  <ul className="space-y-1">{result.analysis.potential_biases.map((b, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-orange-600"><AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />{b}</li>
                  ))}</ul>
                </div>
              )}
              {result.analysis.recommendation && (
                <div className="mt-4 p-3 bg-teal-50 border border-teal-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-1"><Shield className="h-4 w-4 text-teal-600" /><h4 className="text-sm font-semibold text-teal-700">Recommendation</h4></div>
                  <p className="text-sm text-teal-800">{result.analysis.recommendation}</p>
                </div>
              )}

              <div className="mt-4 pt-3 border-t border-gray-200 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => openAssistant(`Explain this research analysis for \"${result.document.title || "this document"}\" in plain language and highlight what is strong vs uncertain.`)}
                  className="px-3 py-1.5 text-xs rounded-full bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 transition-colors"
                >
                  Explain this result in chat
                </button>
                <button
                  type="button"
                  onClick={() => openAssistant(`Based on this report analysis, suggest follow-up deep-search questions that improve evidence triangulation and scientific rigor.`)}
                  className="px-3 py-1.5 text-xs rounded-full bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 transition-colors"
                >
                  Suggest follow-up questions
                </button>
              </div>
              {result.analysis.topics.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">{result.analysis.topics.map((t) => (
                  <span key={t} className="px-2.5 py-1 bg-gray-100 text-gray-600 text-xs rounded-full border border-gray-200">{t}</span>
                ))}</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
