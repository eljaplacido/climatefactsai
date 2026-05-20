"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, Loader2, Search, ExternalLink } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface CompanyRow {
  company_id: string;
  name: string;
  ticker?: string;
  country_code?: string;
  sector_nace?: string;
  disclosure_count: number;
  latest_disclosure_year?: number;
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/companies?limit=200`);
        if (res.ok) {
          const data = await res.json();
          setCompanies(data.companies || []);
        }
      } catch {
        // degrade
      }
      setLoading(false);
    })();
  }, []);

  const filtered = q
    ? companies.filter(
        (c) =>
          c.name.toLowerCase().includes(q.toLowerCase()) ||
          (c.ticker || "").toLowerCase().includes(q.toLowerCase())
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
        <header className="mb-8">
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

        <div className="mb-6">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by company name or ticker..."
              className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-gray-500 py-8">
            <Loader2 className="w-5 h-5 animate-spin" /> Loading companies...
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-gray-500 py-8 text-sm">
            No company data ingested yet. Run the CDP, SBTi, and NZT adapters to populate.
          </div>
        ) : (
          <div className="grid gap-3">
            {filtered.map((c) => (
              <Link
                key={c.company_id}
                href={`/companies/${c.ticker || c.company_id}`}
                className="block bg-white rounded-lg border border-gray-200 hover:border-teal-300 hover:shadow-sm transition-all p-4"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                      {c.name}
                      {c.ticker && (
                        <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                          {c.ticker}
                        </span>
                      )}
                    </h3>
                    <div className="text-xs text-gray-500 mt-1">
                      {c.country_code && `${c.country_code} · `}
                      {c.sector_nace && `${c.sector_nace} · `}
                      {c.disclosure_count} disclosure{c.disclosure_count !== 1 ? "s" : ""}
                      {c.latest_disclosure_year && ` · latest ${c.latest_disclosure_year}`}
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-gray-400 flex-shrink-0" />
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
