"use client";

// F9e — compare two companies side by side. Reads ?a=<ticker>&b=<ticker>,
// fetches both via the existing /api/companies/{ticker} endpoint, and renders
// a side-by-side climate-disclosure comparison (SBTi, net-zero, latest scopes,
// frameworks aligned). Modeled on the deep-search Suspense pattern.

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Building2, Loader2, CheckCircle, XCircle, ArrowLeft } from "lucide-react";

export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface CompanyDetail {
  company_id: string;
  name: string;
  ticker?: string;
  country_code?: string;
  sector_nace?: string;
  disclosure_count: number;
  latest_disclosure_year?: number;
  sbti_validated: boolean;
  net_zero_target_year?: number;
}

interface Disclosure {
  reporting_year: number;
  scope1_tco2e?: number;
  scope2_tco2e_market?: number;
  scope3_tco2e?: number;
}

interface StandardCompliance {
  id: string;
  status: string;
}

interface Loaded {
  company: CompanyDetail | null;
  disclosures: Disclosure[];
  standards: StandardCompliance[];
}

async function loadCompany(ticker: string): Promise<Loaded> {
  const res = await fetch(`${API_BASE}/api/companies/${ticker}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`Failed to load "${ticker}"`);
  const data = await res.json();
  return {
    company: data.company || null,
    disclosures: data.disclosures || [],
    standards: data.standards_compliance || [],
  };
}

function latestDisclosure(d: Disclosure[]): Disclosure | null {
  if (!d.length) return null;
  return [...d].sort((a, b) => (b.reporting_year || 0) - (a.reporting_year || 0))[0];
}

function fmt(n?: number): string {
  return n != null ? `${Math.round(n).toLocaleString()} t` : "—";
}

function BoolCell({ value }: { value: boolean }) {
  return value ? (
    <span className="inline-flex items-center gap-1 text-emerald-700">
      <CheckCircle className="h-4 w-4" /> Yes
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-gray-400">
      <XCircle className="h-4 w-4" /> No
    </span>
  );
}

function CompareInner() {
  const sp = useSearchParams();
  const a = sp.get("a") || "";
  const b = sp.get("b") || "";

  const [left, setLeft] = useState<Loaded | null>(null);
  const [right, setRight] = useState<Loaded | null>(null);
  const [tickerB, setTickerB] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!a || !b) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([loadCompany(a), loadCompany(b)])
      .then(([l, r]) => {
        if (!cancelled) {
          setLeft(l);
          setRight(r);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Failed to load companies");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [a, b]);

  // Prompt for the second company when only one is provided.
  if (a && !b) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <Link href={`/companies/${a}`} className="inline-flex items-center gap-1 text-teal-700 hover:underline mb-4">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Compare with another company</h1>
        <p className="text-gray-600 mb-4">Enter a second company ticker to compare against <strong>{a}</strong>.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (tickerB.trim()) {
              window.location.href = `/companies/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(tickerB.trim())}`;
            }
          }}
          className="flex gap-2"
        >
          <input
            value={tickerB}
            onChange={(e) => setTickerB(e.target.value)}
            placeholder="e.g. MSFT"
            className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50"
          />
          <button type="submit" className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700">
            Compare
          </button>
        </form>
      </div>
    );
  }

  if (!a || !b) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Compare companies</h1>
        <p className="text-gray-600">
          Add two company tickers to the URL, e.g.{" "}
          <code className="bg-gray-100 px-1.5 py-0.5 rounded">/companies/compare?a=TICKER1&amp;b=TICKER2</code>,
          or open a company and use its &quot;Compare&quot; action.
        </p>
        <Link href="/companies" className="inline-flex items-center gap-1 text-teal-700 hover:underline mt-4">
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

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-10">
        <p className="text-rose-700 bg-rose-50 border border-rose-200 rounded p-3">{error}</p>
        <Link href="/companies" className="inline-flex items-center gap-1 text-teal-700 hover:underline mt-4">
          <ArrowLeft className="h-4 w-4" /> Back to companies
        </Link>
      </div>
    );
  }

  const cl = left?.company;
  const cr = right?.company;
  const dl = latestDisclosure(left?.disclosures || []);
  const dr = latestDisclosure(right?.disclosures || []);

  const rows: Array<{ label: string; l: React.ReactNode; r: React.ReactNode }> = [
    { label: "Country", l: cl?.country_code || "—", r: cr?.country_code || "—" },
    { label: "Sector", l: cl?.sector_nace || "—", r: cr?.sector_nace || "—" },
    { label: "SBTi validated", l: <BoolCell value={!!cl?.sbti_validated} />, r: <BoolCell value={!!cr?.sbti_validated} /> },
    { label: "Net-zero target year", l: cl?.net_zero_target_year || "—", r: cr?.net_zero_target_year || "—" },
    { label: "Disclosures on file", l: cl?.disclosure_count ?? 0, r: cr?.disclosure_count ?? 0 },
    { label: "Latest disclosure year", l: cl?.latest_disclosure_year || "—", r: cr?.latest_disclosure_year || "—" },
    { label: "Scope 1 (latest)", l: fmt(dl?.scope1_tco2e), r: fmt(dr?.scope1_tco2e) },
    { label: "Scope 2 (latest)", l: fmt(dl?.scope2_tco2e_market), r: fmt(dr?.scope2_tco2e_market) },
    { label: "Scope 3 (latest)", l: fmt(dl?.scope3_tco2e), r: fmt(dr?.scope3_tco2e) },
    {
      label: "Frameworks aligned",
      l: (left?.standards || []).filter((s) => s.status === "aligned").length,
      r: (right?.standards || []).filter((s) => s.status === "aligned").length,
    },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <Link href="/companies" className="inline-flex items-center gap-1 text-teal-700 hover:underline mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to companies
      </Link>
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <Building2 className="h-6 w-6 text-teal-600" /> Company comparison
      </h1>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-medium text-gray-500 w-1/3">Metric</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-900">
                <Link href={`/companies/${cl?.ticker || a}`} className="hover:text-teal-700">
                  {cl?.name || a}
                </Link>
              </th>
              <th className="text-left px-4 py-3 font-semibold text-gray-900">
                <Link href={`/companies/${cr?.ticker || b}`} className="hover:text-teal-700">
                  {cr?.name || b}
                </Link>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={i % 2 ? "bg-white" : "bg-gray-50/40"}>
                <td className="px-4 py-2.5 text-gray-500">{row.label}</td>
                <td className="px-4 py-2.5 text-gray-900">{row.l}</td>
                <td className="px-4 py-2.5 text-gray-900">{row.r}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400 mt-3">
        Comparison reflects disclosed data on file. &quot;—&quot; means the metric was not
        reported. Latest figures are from each company&apos;s most recent disclosure year.
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
