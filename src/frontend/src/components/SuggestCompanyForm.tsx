"use client";

// Stage 5 / M6 — "Suggest a company" advanced-user form.
//
// Submits to POST /api/companies/suggestions. Auto-matches against
// existing companies and surfaces a deep-link when found; otherwise
// queues for analyst review.
//
// Optional report_url field is the hook for the "analyze this PDF"
// follow-up flow at POST /api/companies/{ticker}/analyze-report.

import { useState } from "react";
import Link from "next/link";
import { Plus, Check, X, Loader2, ExternalLink } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface SubmitResult {
  status: "matched" | "queued";
  matched_company_id: string | null;
  matched_company_name: string | null;
  duplicate_of: string | null;
  note: string;
}

export default function SuggestCompanyForm() {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [ticker, setTicker] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [website, setWebsite] = useState("");
  const [reportUrl, setReportUrl] = useState("");
  const [reason, setReason] = useState("");

  const reset = () => {
    setCompanyName("");
    setTicker("");
    setCountryCode("");
    setWebsite("");
    setReportUrl("");
    setReason("");
    setResult(null);
    setError(null);
  };

  const submit = async () => {
    if (!companyName || companyName.trim().length < 2) {
      setError("Company name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("clilens_token") : null;
      if (!token) {
        setError("Sign in first — suggestions are tied to a user account.");
        setSubmitting(false);
        return;
      }
      const res = await fetch(`${API_BASE}/api/companies/suggestions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          company_name: companyName.trim(),
          ticker: ticker.trim() || null,
          country_code: countryCode.trim().toUpperCase() || null,
          website: website.trim() || null,
          report_url: reportUrl.trim() || null,
          reason: reason.trim() || null,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 120)}`);
      }
      const r: SubmitResult = await res.json();
      setResult(r);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-teal-600 text-white rounded-md hover:bg-teal-700"
      >
        <Plus className="h-4 w-4" />
        Suggest a company
      </button>
    );
  }

  return (
    <section className="bg-white border border-teal-200 rounded-xl p-5 mb-6">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold text-gray-900">
            Suggest a company for the tracker
          </h3>
          <p className="text-xs text-gray-600 mt-0.5">
            Optionally include a sustainability report URL — once accepted,
            the analyst runs /companies/{"{ticker}"}/analyze-report on it.
          </p>
        </div>
        <button
          onClick={() => {
            reset();
            setOpen(false);
          }}
          className="text-gray-500 hover:text-gray-900"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {result ? (
        <div className={`p-4 rounded-md border ${
          result.status === "matched"
            ? "bg-emerald-50 border-emerald-200"
            : "bg-blue-50 border-blue-200"
        }`}>
          <div className="flex items-start gap-2">
            <Check className="h-4 w-4 text-emerald-700 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-900">
                {result.status === "matched" ? "Already in tracker" : "Queued for review"}
              </p>
              <p className="text-xs text-gray-700 mt-1">{result.note}</p>
              {result.matched_company_id && (
                <Link
                  href={`/companies/${result.matched_company_id}`}
                  className="inline-flex items-center gap-1 mt-2 text-sm text-teal-700 hover:underline"
                >
                  Open {result.matched_company_name}
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              )}
            </div>
          </div>
          <button
            onClick={reset}
            className="mt-3 text-xs text-gray-600 hover:text-gray-900 underline"
          >
            Submit another
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <label className="block">
              <span className="text-xs text-gray-700 font-medium">Company name *</span>
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Fazer Group"
                maxLength={200}
                className="mt-1 w-full px-2 py-1.5 text-sm border border-gray-200 rounded-md"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-700 font-medium">Ticker (if listed)</span>
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="e.g. FAZER.HE"
                maxLength={20}
                className="mt-1 w-full px-2 py-1.5 text-sm border border-gray-200 rounded-md"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-700 font-medium">Country (ISO-2)</span>
              <input
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value)}
                placeholder="FI"
                maxLength={2}
                className="mt-1 w-full px-2 py-1.5 text-sm border border-gray-200 rounded-md uppercase"
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-700 font-medium">Website</span>
              <input
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://www.fazer.com"
                maxLength={500}
                className="mt-1 w-full px-2 py-1.5 text-sm border border-gray-200 rounded-md"
              />
            </label>
          </div>
          <label className="block">
            <span className="text-xs text-gray-700 font-medium">
              Sustainability report URL (optional)
            </span>
            <input
              value={reportUrl}
              onChange={(e) => setReportUrl(e.target.value)}
              placeholder="https://www.fazer.com/.../fazer-annual-report-2025.pdf"
              maxLength={500}
              className="mt-1 w-full px-2 py-1.5 text-sm border border-gray-200 rounded-md"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-700 font-medium">
              Why track this company? (optional)
            </span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Have a 2030 net-zero claim I want verified against their Scope 3 disclosures"
              maxLength={1000}
              rows={3}
              className="mt-1 w-full px-2 py-1.5 text-sm border border-gray-200 rounded-md"
            />
          </label>
          {error && (
            <p className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded px-2 py-1">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={() => {
                reset();
                setOpen(false);
              }}
              className="px-3 py-1.5 text-sm text-gray-700 border border-gray-200 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-teal-600 text-white rounded-md hover:bg-teal-700 disabled:opacity-50"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Submit
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
