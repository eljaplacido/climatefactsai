"use client";

// Recent worked research analyses — Stage 3 / Slice 3 of audit.
//
// User complaint: "Researches still show just release feed but no
// insights reports like from articles." The /research page surfaced
// the subscription feed + upload form, but completed url_analyses
// were invisible. This component lists them at the top of the page
// so users can see what analyses HAVE happened on the platform.
//
// Each analysis links to the audit-trail page that already exists
// at /api/methodology/audit-trail/url-analysis/{analysis_id}.

import { useEffect, useState } from "react";
import { FileText, ExternalLink, Loader2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Analysis {
  analysis_id: string;
  submitted_url: string | null;
  status: string;
  overall_credibility: string | null;
  reliability_score: number | null;
  processing_time_ms: number | null;
  created_at: string | null;
  completed_at: string | null;
}

function CredibilityBadge({ level }: { level: string | null }) {
  const cls =
    level === "HIGH"
      ? "bg-emerald-50 border-emerald-200 text-emerald-700"
      : level === "MEDIUM"
      ? "bg-amber-50 border-amber-200 text-amber-700"
      : level === "LOW"
      ? "bg-rose-50 border-rose-200 text-rose-700"
      : "bg-gray-50 border-gray-200 text-gray-600";
  return (
    <span className={`text-[10px] uppercase tracking-wide font-semibold px-1.5 py-0.5 rounded border ${cls}`}>
      {level || "UNKNOWN"}
    </span>
  );
}

function truncateUrl(u: string | null, limit = 80): string {
  if (!u) return "—";
  if (u.length <= limit) return u;
  return u.slice(0, limit - 1) + "…";
}

export default function RecentResearchAnalyses() {
  const [data, setData] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/research/analyses?limit=12`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setData(d.analyses || []);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <section className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-clilens-primary" />
          <span className="text-sm text-gray-600">Loading recent research analyses…</span>
        </div>
      </section>
    );
  }

  if (data.length === 0) {
    return (
      <section className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
        <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <FileText className="h-4 w-4 text-clilens-primary" />
          Recent worked analyses
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          No analyses completed yet. Submit a URL or DOI below to start one — once
          it finishes the analysis lands in this panel for everyone to learn from.
        </p>
      </section>
    );
  }

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <FileText className="h-4 w-4 text-clilens-primary" />
          Recent worked analyses ({data.length})
        </h2>
        <p className="text-xs text-gray-500">
          Climate-research URLs the platform has scored end-to-end.
        </p>
      </div>
      <ul className="space-y-1.5">
        {data.map((a) => (
          <li
            key={a.analysis_id}
            className="bg-gray-50 border border-gray-100 rounded-md px-3 py-2 hover:bg-white hover:border-gray-300 transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <a
                  href={a.submitted_url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-900 font-medium hover:text-clilens-primary truncate flex items-center gap-1"
                  title={a.submitted_url || ""}
                >
                  <span className="truncate">{truncateUrl(a.submitted_url, 90)}</span>
                  {a.submitted_url && <ExternalLink className="h-3 w-3 flex-shrink-0 text-gray-400" />}
                </a>
                <div className="text-[11px] text-gray-500 mt-0.5 flex items-center gap-2">
                  <CredibilityBadge level={a.overall_credibility} />
                  {a.reliability_score != null && (
                    <span>reliability {a.reliability_score}/100</span>
                  )}
                  {a.completed_at && (
                    <span>· {a.completed_at.slice(0, 10)}</span>
                  )}
                  {a.processing_time_ms && (
                    <span>· {(a.processing_time_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>
              </div>
              <a
                href={`${API_BASE}/api/methodology/audit-trail/url-analysis/${a.analysis_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-clilens-primary hover:underline whitespace-nowrap flex-shrink-0"
              >
                Audit trail ↗
              </a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
