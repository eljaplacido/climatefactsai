"use client";

// F9e — head-to-head climate comparison of two companies. Reads ?a=<ticker|id>&b=<ticker|id>
// and renders the purpose-built /api/companies/compare endpoint (seq-13): a size-INDEPENDENT
// "ambition" verdict (SBTi validation, net-zero year, % reduction target, scope-1/2 assurance)
// with a declared leader per dimension, plus absolute scope emissions shown WITHOUT a leader
// (absolute tonnage scales with company size, so "lower" ≠ "greener"). Suspense pattern mirrors
// the deep-search page.

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Building2, Loader2, CheckCircle, XCircle, ArrowLeft, Trophy, Minus } from "lucide-react";
import SaveButton from "@/components/SaveButton";
import CompanySearch from "@/components/CompanySearch";

export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type Side = "a" | "b" | "tie" | null;

interface CompanyMetrics {
  company_id: string;
  name: string;
  ticker?: string;
  country_code?: string;
  sector_nace?: string;
  disclosure_count: number;
  sbti_validated: boolean;
  net_zero_target_year?: number | null;
  target_pct_reduction?: number | null;
  target_year?: number | null;
  scope1_2_verified: boolean;
  scope1_tco2e?: number | null;
  scope2_tco2e_market?: number | null;
  scope3_tco2e?: number | null;
}

interface Dim {
  a: number | boolean | null;
  b: number | boolean | null;
  leader: Side;
}

interface CompareResult {
  company_a: CompanyMetrics;
  company_b: CompanyMetrics;
  comparison: Record<string, Dim>;
  emissions: {
    note: string;
    scope1_tco2e: { a: number | null; b: number | null };
    scope2_tco2e_market: { a: number | null; b: number | null };
    scope3_tco2e: { a: number | null; b: number | null };
  };
  ambition_leader: Side;
  ambition_dimensions_won: { a: number; b: number };
}

async function loadComparison(a: string, b: string): Promise<CompareResult> {
  const res = await fetch(
    `${API_BASE}/api/companies/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    { headers: { Accept: "application/json" } }
  );
  if (!res.ok) {
    let detail = `Failed to compare (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json();
}

function fmtTonnes(n?: number | null): string {
  return n != null ? `${Math.round(n).toLocaleString()} tCO₂e` : "—";
}

function BoolValue({ value }: { value: boolean | null }) {
  return value ? (
    <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
      <CheckCircle className="h-4 w-4" /> Yes
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-gray-400">
      <XCircle className="h-4 w-4" /> No
    </span>
  );
}

// Each ambition dimension: how to render its value + a one-line "why this matters".
const AMBITION_DIMS: Array<{
  key: string;
  label: string;
  help: string;
  render: (v: number | boolean | null) => React.ReactNode;
}> = [
  {
    key: "sbti_validated",
    label: "SBTi-validated targets",
    help: "Targets independently approved by the Science Based Targets initiative.",
    render: (v) => <BoolValue value={typeof v === "boolean" ? v : false} />,
  },
  {
    key: "net_zero_target_year",
    label: "Net-zero target year",
    help: "An earlier target year signals greater ambition.",
    render: (v) => <span>{v != null && v !== false ? String(v) : "—"}</span>,
  },
  {
    key: "target_pct_reduction",
    label: "Headline reduction target",
    help: "A larger committed cut is more ambitious.",
    render: (v) => <span>{v != null && v !== false ? `${v}%` : "—"}</span>,
  },
  {
    key: "scope1_2_verified",
    label: "Scope 1 & 2 third-party assured",
    help: "Emissions independently verified, not self-reported.",
    render: (v) => <BoolValue value={typeof v === "boolean" ? v : false} />,
  },
];

function LeaderBadge() {
  return (
    <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 align-middle">
      <Trophy className="h-3 w-3" /> Leads
    </span>
  );
}

function cellClass(isLeader: boolean) {
  return isLeader ? "px-4 py-3 bg-emerald-50/70 text-gray-900" : "px-4 py-3 text-gray-900";
}

function VerdictBanner({ result }: { result: CompareResult }) {
  const { ambition_leader, ambition_dimensions_won, company_a, company_b } = result;
  const winner = ambition_leader === "a" ? company_a : ambition_leader === "b" ? company_b : null;
  const won = ambition_leader === "a" ? ambition_dimensions_won.a : ambition_dimensions_won.b;

  if (!winner) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <Minus className="mt-0.5 h-5 w-5 flex-shrink-0 text-slate-500" />
        <div>
          <p className="font-semibold text-slate-800">Evenly matched on climate ambition</p>
          <p className="text-sm text-slate-600">
            Neither company leads on the size-independent ambition dimensions
            ({ambition_dimensions_won.a}–{ambition_dimensions_won.b}).
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
      <Trophy className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" />
      <div>
        <p className="font-semibold text-emerald-900">
          {winner.name} leads on climate ambition
        </p>
        <p className="text-sm text-emerald-800">
          Won {won} of {AMBITION_DIMS.length} size-independent ambition dimensions
          (SBTi validation, net-zero year, reduction target, third-party assurance).
        </p>
      </div>
    </div>
  );
}

function CompareInner() {
  const sp = useSearchParams();
  const a = sp?.get("a") || "";
  const b = sp?.get("b") || "";

  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!a || !b) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    loadComparison(a, b)
      .then((r) => {
        if (!cancelled) setResult(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Failed to load comparison");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [a, b]);

  // One company provided → prompt for the second via searchable dropdown.
  if (a && !b) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <Link href={`/companies/${a}`} className="inline-flex items-center gap-1 text-teal-700 hover:underline mb-4">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Compare with another company</h1>
        <p className="text-gray-600 mb-4">
          Search and select a second company to compare against <strong>{a}</strong>.
        </p>
        <CompanySearch
          onSelect={(company) => {
            window.location.href = `/companies/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(company.ticker)}`;
          }}
          placeholder="Search by company name or ticker..."
          excludeTicker={a}
        />
      </div>
    );
  }

  // No companies selected → prompt for both.
  if (!a || !b) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Compare companies</h1>
        <p className="text-gray-600 mb-6">
          Search for two companies to compare their climate disclosures side-by-side.
        </p>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Company A</label>
            <CompanySearch
              onSelect={(company) => {
                const params = new URLSearchParams(sp?.toString() || "");
                params.set("a", company.ticker);
                window.location.href = `/companies/compare?${params.toString()}`;
              }}
              placeholder="First company..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Company B</label>
            <CompanySearch
              onSelect={(company) => {
                const params = new URLSearchParams(sp?.toString() || "");
                params.set("b", company.ticker);
                window.location.href = `/companies/compare?${params.toString()}`;
              }}
              placeholder="Second company..."
            />
          </div>
        </div>
        <Link href="/companies" className="inline-flex items-center gap-1 text-teal-700 hover:underline mt-6">
          <ArrowLeft className="h-4 w-4" /> Back to companies
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 flex items-center gap-2 text-gray-600">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading comparison…
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-10">
        <p className="text-rose-700 bg-rose-50 border border-rose-200 rounded p-3">
          {error || "No comparison data."}
        </p>
        <Link href="/companies" className="inline-flex items-center gap-1 text-teal-700 hover:underline mt-4">
          <ArrowLeft className="h-4 w-4" /> Back to companies
        </Link>
      </div>
    );
  }

  const { company_a: cl, company_b: cr, comparison, emissions } = result;

  // F10b — save this head-to-head as a "company_comparison". itemRef is "A~B"
  // (the values the compare URL accepts) so /saves can reconstruct the link.
  const saveRef = `${cl.ticker || cl.company_id}~${cr.ticker || cr.company_id}`;
  const saveLabel = `${cl.name || a} vs ${cr.name || b}`;

  const contextRows: Array<{ label: string; l: React.ReactNode; r: React.ReactNode }> = [
    { label: "Country", l: cl.country_code || "—", r: cr.country_code || "—" },
    { label: "Sector (NACE)", l: cl.sector_nace || "—", r: cr.sector_nace || "—" },
    { label: "Disclosures on file", l: cl.disclosure_count ?? 0, r: cr.disclosure_count ?? 0 },
  ];

  const emissionRows: Array<{ label: string; l: string; r: string }> = [
    { label: "Scope 1 (latest)", l: fmtTonnes(emissions.scope1_tco2e.a), r: fmtTonnes(emissions.scope1_tco2e.b) },
    { label: "Scope 2 — market (latest)", l: fmtTonnes(emissions.scope2_tco2e_market.a), r: fmtTonnes(emissions.scope2_tco2e_market.b) },
    { label: "Scope 3 (latest)", l: fmtTonnes(emissions.scope3_tco2e.a), r: fmtTonnes(emissions.scope3_tco2e.b) },
  ];

  const HeaderCell = ({ c, fallback }: { c: CompanyMetrics; fallback: string }) => (
    <Link href={`/companies/${c.ticker || c.company_id}`} className="hover:text-teal-700">
      {c.name || fallback}
      {c.ticker ? <span className="ml-1 text-xs font-normal text-gray-400">{c.ticker}</span> : null}
    </Link>
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <Link href="/companies" className="inline-flex items-center gap-1 text-teal-700 hover:underline mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to companies
      </Link>
      <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Building2 className="h-6 w-6 text-teal-600" /> Company comparison
        </h1>
        <SaveButton type="company_comparison" itemRef={saveRef} label={saveLabel} variant="chip" />
      </div>

      <div className="mb-6">
        <VerdictBanner result={result} />
      </div>

      {/* Ambition — size-independent, leader declared per dimension */}
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Climate ambition
      </h2>
      <div className="overflow-x-auto rounded-lg border border-gray-200 mb-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-medium text-gray-500 w-2/5">Dimension</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-900">
                <HeaderCell c={cl} fallback={a} />
              </th>
              <th className="text-left px-4 py-3 font-semibold text-gray-900">
                <HeaderCell c={cr} fallback={b} />
              </th>
            </tr>
          </thead>
          <tbody>
            {AMBITION_DIMS.map((dim, i) => {
              const d = comparison[dim.key];
              const leader = d?.leader ?? null;
              return (
                <tr key={dim.key} className={i % 2 ? "bg-white" : "bg-gray-50/40"}>
                  <td className="px-4 py-3 align-top">
                    <div className="text-gray-700 font-medium">{dim.label}</div>
                    <div className="text-xs text-gray-400">{dim.help}</div>
                  </td>
                  <td className={cellClass(leader === "a")}>
                    {dim.render(d ? d.a : null)}
                    {leader === "a" ? <LeaderBadge /> : null}
                  </td>
                  <td className={cellClass(leader === "b")}>
                    {dim.render(d ? d.b : null)}
                    {leader === "b" ? <LeaderBadge /> : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Absolute emissions — deliberately NO leader (scales with company size) */}
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Absolute emissions
      </h2>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-medium text-gray-500 w-2/5">Metric</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-900">{cl.name || a}</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-900">{cr.name || b}</th>
            </tr>
          </thead>
          <tbody>
            {emissionRows.map((row, i) => (
              <tr key={row.label} className={i % 2 ? "bg-white" : "bg-gray-50/40"}>
                <td className="px-4 py-2.5 text-gray-500">{row.label}</td>
                <td className="px-4 py-2.5 text-gray-900">{row.l}</td>
                <td className="px-4 py-2.5 text-gray-900">{row.r}</td>
              </tr>
            ))}
            {contextRows.map((row, i) => (
              <tr key={row.label} className={(emissionRows.length + i) % 2 ? "bg-white" : "bg-gray-50/40"}>
                <td className="px-4 py-2.5 text-gray-500">{row.label}</td>
                <td className="px-4 py-2.5 text-gray-900">{row.l}</td>
                <td className="px-4 py-2.5 text-gray-900">{row.r}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-500 mt-3 flex items-start gap-1.5">
        <span aria-hidden>ℹ️</span>
        <span>{emissions.note}</span>
      </p>
      <p className="text-xs text-gray-400 mt-1">
        Comparison reflects disclosed data on file. &quot;—&quot; means the metric was not reported.
        Latest figures are from each company&apos;s most recent disclosure year.
      </p>
    </div>
  );
}

export default function CompareCompaniesPage() {
  return (
    <Suspense fallback={<div className="max-w-5xl mx-auto px-4 py-16 text-gray-500">Loading…</div>}>
      <CompareInner />
    </Suspense>
  );
}
