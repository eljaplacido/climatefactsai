"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Building2,
  Loader2,
  Search,
  ExternalLink,
  ShieldCheck,
  Target,
  Factory,
  TrendingDown,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface CompanyRow {
  company_id: string;
  name: string;
  ticker?: string | null;
  country_code?: string | null;
  sector_nace?: string | null;
  disclosure_count: number;
  latest_disclosure_year?: number | null;
  sbti_validated?: boolean;
  net_zero_target_year?: number | null;
  scope1_tco2e?: number | null;
  scope3_tco2e?: number | null;
  target_pct_reduction?: number | null;
}

interface CompaniesStats {
  total_companies: number;
  with_disclosures: number;
  sbti_validated: number;
  fully_disclosed: number;
}

type SortMode = "richness" | "name" | "recent";

function formatTonnes(n?: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} MtCO2e`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)} ktCO2e`;
  return `${Math.round(n)} tCO2e`;
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [stats, setStats] = useState<CompaniesStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortMode>("richness");
  const [sbtiOnly, setSbtiOnly] = useState(false);
  const [hasClimateData, setHasClimateData] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          limit: "200",
          sort,
          ...(sbtiOnly ? { sbti_only: "true" } : {}),
          ...(hasClimateData ? { has_climate_data: "true" } : {}),
        });
        const res = await fetch(`${API_BASE}/api/companies?${params}`);
        if (res.ok) {
          const data = await res.json();
          setCompanies(data.companies || []);
          setStats(data.stats || null);
        }
      } catch {
        // degrade
      }
      setLoading(false);
    })();
  }, [sort, sbtiOnly, hasClimateData]);

  const filtered = q
    ? companies.filter(
        (c) =>
          c.name.toLowerCase().includes(q.toLowerCase()) ||
          (c.ticker || "").toLowerCase().includes(q.toLowerCase()),
      )
    : companies;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center gap-4">
          <Link href="/" className="text-2xl font-bold text-clilens-primary">
            Climatefacts.ai
          </Link>
          <nav className="text-sm text-gray-500 flex gap-4 ml-auto">
            <Link href="/map" className="hover:text-gray-800">Map</Link>
            <Link href="/companies" className="text-gray-900 font-medium">Companies</Link>
            <Link href="/methodology" className="hover:text-gray-800">Methodology</Link>
          </nav>
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <header className="mb-6">
          <h1 className="text-4xl font-bold text-gray-900 mb-3 flex items-center gap-3">
            <Building2 className="w-8 h-8 text-teal-600" />
            Corporate Climate Tracker
          </h1>
          <p className="text-lg text-gray-600 max-w-3xl">
            Verified corporate climate disclosures, net-zero targets, and
            sustainability claims — sourced from CDP, SBTi, and Net Zero Tracker.
            ECGT-ready: every claim ships with audit-ready evidence.
          </p>
        </header>

        {/* Stats banner — what's actually in the corpus */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <StatTile
              icon={Factory}
              label="Companies tracked"
              value={stats.total_companies.toLocaleString()}
              color="text-gray-900"
            />
            <StatTile
              icon={Building2}
              label="With climate disclosures"
              value={stats.with_disclosures.toLocaleString()}
              color="text-teal-700"
            />
            <StatTile
              icon={ShieldCheck}
              label="SBTi-validated"
              value={stats.sbti_validated.toLocaleString()}
              color="text-emerald-700"
            />
            <StatTile
              icon={Target}
              label="Comprehensive disclosure"
              value={stats.fully_disclosed.toLocaleString()}
              color="text-amber-700"
              hint="SBTi + scope + net-zero year"
            />
          </div>
        )}

        {/* Controls: search + sort + filter */}
        <div className="mb-6 flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by company name or ticker..."
              className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500"
            />
          </div>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortMode)}
            className="border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/50"
            aria-label="Sort companies"
          >
            <option value="richness">Sort: Disclosure depth</option>
            <option value="name">Sort: Name (A-Z)</option>
            <option value="recent">Sort: Recency</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={sbtiOnly}
              onChange={(e) => setSbtiOnly(e.target.checked)}
              className="rounded text-teal-600 focus:ring-teal-500"
            />
            SBTi only
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={hasClimateData}
              onChange={(e) => setHasClimateData(e.target.checked)}
              className="rounded text-teal-600 focus:ring-teal-500"
            />
            Climate data only
          </label>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-gray-500 py-8">
            <Loader2 className="w-5 h-5 animate-spin" /> Loading companies...
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-gray-500 py-8 text-sm bg-white border border-gray-200 rounded-lg p-6 text-center">
            <p>No companies match the current filters.</p>
            <p className="text-xs mt-1">
              {stats?.total_companies ? `${stats.total_companies.toLocaleString()} companies tracked — try clearing filters or search.` : null}
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {filtered.map((c) => (
              <Link
                key={c.company_id}
                href={`/companies/${c.ticker || c.company_id}`}
                className="block bg-white rounded-lg border border-gray-200 hover:border-teal-300 hover:shadow-sm transition-all p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 flex items-center gap-2 flex-wrap">
                      <span className="truncate">{c.name}</span>
                      {c.ticker && (
                        <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                          {c.ticker}
                        </span>
                      )}
                      {c.sbti_validated && (
                        <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded inline-flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3" /> SBTi validated
                        </span>
                      )}
                      {c.net_zero_target_year && (
                        <span className="text-[10px] bg-teal-50 text-teal-700 border border-teal-200 px-1.5 py-0.5 rounded inline-flex items-center gap-1">
                          <Target className="w-3 h-3" /> Net zero {c.net_zero_target_year}
                        </span>
                      )}
                    </h3>
                    <div className="text-xs text-gray-500 mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
                      {c.country_code && <span>{c.country_code}</span>}
                      {c.sector_nace && <span>{c.sector_nace}</span>}
                      <span>
                        {c.disclosure_count} disclosure{c.disclosure_count !== 1 ? "s" : ""}
                      </span>
                      {c.latest_disclosure_year && <span>latest {c.latest_disclosure_year}</span>}
                    </div>
                    {/* Climate data preview row */}
                    {(c.scope1_tco2e || c.scope3_tco2e || c.target_pct_reduction) && (
                      <div className="flex flex-wrap gap-3 mt-2 text-xs">
                        {c.scope1_tco2e != null && (
                          <span className="text-gray-700">
                            <strong>Scope 1:</strong> {formatTonnes(c.scope1_tco2e)}
                          </span>
                        )}
                        {c.scope3_tco2e != null && (
                          <span className="text-gray-700">
                            <strong>Scope 3:</strong> {formatTonnes(c.scope3_tco2e)}
                          </span>
                        )}
                        {c.target_pct_reduction != null && (
                          <span className="text-emerald-700 inline-flex items-center gap-1">
                            <TrendingDown className="w-3 h-3" />
                            −{c.target_pct_reduction}% target
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <ExternalLink className="w-4 h-4 text-gray-400 flex-shrink-0 mt-1" />
                </div>
              </Link>
            ))}
          </div>
        )}

        <footer className="mt-12 text-xs text-gray-500 border-t border-gray-200 pt-6">
          Data sources: CDP, SBTi, Net Zero Tracker. Datasets are public.
          See{" "}
          <Link href="/methodology" className="text-teal-700 hover:underline">
            Methodology
          </Link>{" "}
          for the full corporate-claim verification pipeline.
        </footer>
      </main>
    </div>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
  color,
  hint,
}: {
  icon: any;
  label: string;
  value: string;
  color: string;
  hint?: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-3">
      <div className="flex items-center justify-between">
        <Icon className="w-4 h-4 text-gray-400" />
      </div>
      <div className={`text-2xl font-bold mt-1.5 ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
      {hint && <div className="text-[10px] text-gray-400 mt-0.5 italic">{hint}</div>}
    </div>
  );
}
