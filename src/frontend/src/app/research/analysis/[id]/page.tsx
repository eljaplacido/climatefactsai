"use client";

// F8a — readable research-analysis report. Replaces the raw provenance-JSON
// link the "Recent worked analyses" panel used to point at. Renders one
// completed url_analyses run as a human report: title, source, credibility,
// extracted claims, fact-checks, and the UN SDGs it touches. The technical
// provenance JSON is kept as a small secondary link for auditors.

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ExternalLink, FileText, Loader2, ShieldCheck, CheckCircle, XCircle, HelpCircle } from "lucide-react";
import SDGChips from "@/components/SDGChips";

export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type ClaimLike = string | { text?: string; claim_text?: string; claim?: string; claim_type?: string };
interface FactCheck {
  claim?: string;
  claim_text?: string;
  verdict?: string;
  verification_status?: string;
  confidence?: number;
  explanation?: string;
  reasoning?: string;
  evidence?: string;
  source?: string;
}

interface Report {
  analysis_id: string;
  submitted_url: string | null;
  title: string | null;
  source_name: string | null;
  status: string;
  overall_credibility: string | null;
  reliability_score: number | null;
  claims: ClaimLike[];
  fact_checks: FactCheck[];
  evidence: unknown[];
  processing_time_ms: number | null;
  created_at: string | null;
  completed_at: string | null;
}

function claimText(c: ClaimLike): string {
  if (typeof c === "string") return c;
  return c.text || c.claim_text || c.claim || "";
}

function credClasses(level: string | null): string {
  return level === "HIGH"
    ? "bg-emerald-50 border-emerald-200 text-emerald-700"
    : level === "MEDIUM"
    ? "bg-amber-50 border-amber-200 text-amber-700"
    : level === "LOW"
    ? "bg-rose-50 border-rose-200 text-rose-700"
    : "bg-gray-50 border-gray-200 text-gray-600";
}

function VerdictIcon({ verdict }: { verdict: string }) {
  const v = verdict.toLowerCase();
  if (v.includes("true") || v === "verified" || v === "supported")
    return <CheckCircle className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />;
  if (v.includes("false") || v === "disputed" || v === "refuted")
    return <XCircle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />;
  return <HelpCircle className="h-4 w-4 text-gray-400 flex-shrink-0 mt-0.5" />;
}

export default function ResearchAnalysisReportPage() {
  const params = useParams();
  const id = (params?.id as string) || "";

  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/research/analyses/${id}`, { headers: { Accept: "application/json" } })
      .then(async (r) => {
        if (!r.ok) {
          if (r.status === 404) throw new Error("This analysis isn't available (not found or not completed).");
          throw new Error(`Could not load the analysis (${r.status}).`);
        }
        return r.json();
      })
      .then((d) => {
        if (!cancelled) setReport(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Could not load the analysis.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 flex items-center gap-2 text-gray-600">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading analysis…
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12">
        <Link href="/research" className="inline-flex items-center gap-1 text-teal-700 hover:underline mb-4">
          <ArrowLeft className="h-4 w-4" /> Back to research
        </Link>
        <p className="text-rose-700 bg-rose-50 border border-rose-200 rounded p-3">
          {error || "No analysis data."}
        </p>
      </div>
    );
  }

  const claims = (report.claims || []).map(claimText).filter(Boolean);
  const factChecks = report.fact_checks || [];
  const sdgText = [report.title || "", ...claims].join(" ");

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <Link href="/research" className="inline-flex items-center gap-1 text-teal-700 hover:underline mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to research
      </Link>

      <header className="mb-6">
        <div className="flex items-center gap-2 text-xs text-gray-400 uppercase tracking-wide mb-1">
          <FileText className="h-3.5 w-3.5" /> Research analysis report
        </div>
        <h1 className="text-2xl font-bold text-gray-900">
          {report.title || report.submitted_url || "Untitled analysis"}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-gray-500">
          {report.source_name && <span>{report.source_name}</span>}
          {report.completed_at && <span>· {report.completed_at.slice(0, 10)}</span>}
          {report.submitted_url && (
            <a
              href={report.submitted_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-teal-700 hover:underline"
            >
              Original source <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </header>

      {/* Credibility scorecard */}
      <section className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <ShieldCheck className="h-5 w-5 text-teal-600" />
          <span className={`text-xs uppercase tracking-wide font-semibold px-2 py-0.5 rounded border ${credClasses(report.overall_credibility)}`}>
            {report.overall_credibility || "UNKNOWN"} credibility
          </span>
          {report.reliability_score != null && (
            <span className="text-sm text-gray-700">
              Reliability <strong>{report.reliability_score}/100</strong>
            </span>
          )}
          <span className="text-xs text-gray-400">
            {claims.length} claim{claims.length === 1 ? "" : "s"} · {factChecks.length} fact-check{factChecks.length === 1 ? "" : "s"}
          </span>
        </div>
      </section>

      {/* UN SDGs */}
      {sdgText.trim().length > 10 && (
        <section className="mb-6">
          <SDGChips text={sdgText} maxChips={5} minMatchCount={1} />
        </section>
      )}

      {/* Fact-checks (preferred — they carry a verdict) */}
      {factChecks.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Claims &amp; fact-checks</h2>
          <div className="space-y-2.5">
            {factChecks.map((fc, i) => {
              const verdict = fc.verdict || fc.verification_status || "unverified";
              const text = fc.claim || fc.claim_text || claims[i] || `Claim ${i + 1}`;
              const why = fc.explanation || fc.reasoning;
              return (
                <div key={i} className="rounded-lg border border-gray-200 bg-white p-3">
                  <div className="flex items-start gap-2">
                    <VerdictIcon verdict={verdict} />
                    <div className="min-w-0">
                      <p className="text-sm text-gray-900">{text}</p>
                      <div className="mt-1 flex items-center gap-2 text-xs">
                        <span className="font-medium text-gray-700">{verdict.replace(/_/g, " ")}</span>
                        {fc.confidence != null && (
                          <span className="text-gray-400">· {Math.round((fc.confidence > 1 ? fc.confidence : fc.confidence * 100))}% confidence</span>
                        )}
                      </div>
                      {why && <p className="text-xs text-gray-500 mt-1">{why}</p>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Extracted claims with no fact-check pairing */}
      {factChecks.length === 0 && claims.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Extracted claims</h2>
          <ul className="space-y-2">
            {claims.map((c, i) => (
              <li key={i} className="rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-900">
                {c}
              </li>
            ))}
          </ul>
        </section>
      )}

      {claims.length === 0 && factChecks.length === 0 && (
        <p className="text-sm text-gray-500 mb-6">
          No claims were extracted from this source. The credibility score above
          reflects source-level signals only.
        </p>
      )}

      {/* Secondary: technical provenance for auditors */}
      <p className="text-xs text-gray-400 border-t border-gray-200 pt-3">
        For the technical record (model, prompts, sources used),{" "}
        <a
          href={`${API_BASE}/api/methodology/audit-trail/url-analysis/${report.analysis_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-500 hover:underline"
        >
          view the provenance JSON
        </a>
        {report.processing_time_ms != null && <> · analysed in {(report.processing_time_ms / 1000).toFixed(1)}s</>}.
      </p>
    </div>
  );
}
