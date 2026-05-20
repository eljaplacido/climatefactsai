"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Building2, Loader2, CheckCircle, AlertTriangle, XCircle,
  HelpCircle, FileText, ExternalLink, ArrowLeft,
} from "lucide-react";

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
  disclosure_id: string;
  source: string;
  reporting_year: number;
  scope1_tco2e?: number;
  scope2_tco2e_market?: number;
  scope2_tco2e_location?: number;
  scope3_tco2e?: number;
  scope1_2_verified: boolean;
  sbti_validated: boolean;
  target_year?: number;
  baseline_year?: number;
  target_pct_reduction?: number;
  net_zero_target_year?: number;
  offset_based_claims?: string;
  assurance_level?: string;
  assurance_provider?: string;
}

interface Claim {
  claim_id: string;
  claim_text: string;
  claim_type: string;
  verdict: string;
  flag_reason?: string;
  evidence_url?: string;
  created_at?: string;
}

export default function CompanyDetailPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = params?.ticker;
  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [disclosures, setDisclosures] = useState<Disclosure[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzeText, setAnalyzeText] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/companies/${ticker}`);
        if (!res.ok) throw new Error("Not found");
        const data = await res.json();
        setCompany(data.company);
        setDisclosures(data.disclosures || []);
        setClaims(data.claims || []);
      } catch {
        setCompany(null);
      }
      setLoading(false);
    })();
  }, [ticker]);

  const handleAnalyze = async () => {
    if (!analyzeText.trim() || analyzing) return;
    setAnalyzing(true);
    try {
      const res = await fetch(`${API_BASE}/api/companies/${ticker}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim_text: analyzeText }),
      });
      if (res.ok) {
        const result = await res.json();
        setClaims((prev) => [
          {
            claim_id: result.claim_id,
            claim_text: result.claim_text,
            claim_type: result.claim_type,
            verdict: result.verdict,
            flag_reason: result.flag_reason,
            evidence_url: result.evidence,
            created_at: new Date().toISOString(),
          },
          ...prev,
        ]);
        setAnalyzeText("");
      }
    } catch {
      // degrade
    }
    setAnalyzing(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
      </div>
    );
  }

  if (!company) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h2 className="text-xl font-semibold text-gray-700">Company not found</h2>
          <Link href="/companies" className="text-teal-700 hover:underline text-sm mt-2 inline-block">
            Back to company index
          </Link>
        </div>
      </div>
    );
  }

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
        <Link href="/companies" className="text-sm text-teal-700 hover:underline inline-flex items-center gap-1 mb-6">
          <ArrowLeft className="w-3 h-3" /> Back to company index
        </Link>

        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            {company.name}
            {company.ticker && (
              <span className="text-lg bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono">
                {company.ticker}
              </span>
            )}
          </h1>
          <div className="flex flex-wrap gap-4 mt-3 text-sm">
            {company.country_code && (
              <span className="text-gray-600">Country: {company.country_code}</span>
            )}
            {company.sector_nace && (
              <span className="text-gray-600">{company.sector_nace}</span>
            )}
            <span className="text-gray-600">
              {company.disclosure_count} disclosure{company.disclosure_count !== 1 ? "s" : ""}
            </span>
            <span className={`font-medium ${company.sbti_validated ? "text-teal-700" : "text-amber-700"}`}>
              SBTi: {company.sbti_validated ? "Validated" : "Not validated"}
            </span>
            {company.net_zero_target_year && (
              <span className="text-gray-600">
                Net-zero target: {company.net_zero_target_year}
              </span>
            )}
          </div>
        </header>

        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-teal-600" />
                Climate Disclosures
              </h2>
              {disclosures.length === 0 ? (
                <p className="text-sm text-gray-500">No disclosures ingested yet.</p>
              ) : (
                <div className="space-y-3">
                  {disclosures.map((d) => (
                    <div key={d.disclosure_id} className="bg-white rounded-lg border border-gray-200 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold uppercase bg-teal-100 text-teal-700 px-2 py-0.5 rounded">
                          {d.source} · {d.reporting_year}
                        </span>
                        {d.scope1_2_verified ? (
                          <span className="text-xs text-teal-700 flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> Verified
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">Unverified</span>
                        )}
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <div>
                          <span className="text-gray-500">Scope 1</span>
                          <div className="font-mono text-gray-900">{d.scope1_tco2e?.toLocaleString() ?? "—"} t</div>
                        </div>
                        <div>
                          <span className="text-gray-500">Scope 2</span>
                          <div className="font-mono text-gray-900">{d.scope2_tco2e_market?.toLocaleString() ?? "—"} t</div>
                        </div>
                        <div>
                          <span className="text-gray-500">Scope 3</span>
                          <div className="font-mono text-gray-900">{d.scope3_tco2e?.toLocaleString() ?? "—"} t</div>
                        </div>
                      </div>
                      {d.target_pct_reduction && (
                        <div className="mt-2 text-xs text-gray-600">
                          Target: {d.target_pct_reduction}% reduction by {d.target_year}
                          {d.baseline_year && ` (baseline ${d.baseline_year})`}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                Verify a Claim
              </h2>
              <p className="text-sm text-gray-600 mb-3">
                Submit a corporate climate claim for verification against disclosed data and regulatory standards (ECGT, CSRD, SBTi).
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={analyzeText}
                  onChange={(e) => setAnalyzeText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                  placeholder='e.g. "We are carbon neutral by 2030 using offsets"'
                  className="flex-1 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50"
                  disabled={analyzing}
                />
                <button
                  onClick={handleAnalyze}
                  disabled={!analyzeText.trim() || analyzing}
                  className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-500 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify"}
                </button>
              </div>
            </section>
          </div>

          <aside>
            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                Verified Claims
              </h2>
              {claims.length === 0 ? (
                <p className="text-sm text-gray-500">No claims verified yet.</p>
              ) : (
                <div className="space-y-3">
                  {claims.map((c) => (
                    <div key={c.claim_id} className="bg-white rounded-lg border border-gray-200 p-3">
                      <div className="flex items-start gap-2 mb-1">
                        {c.verdict === "verified" && <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />}
                        {c.verdict === "disputed" && <XCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />}
                        {c.verdict === "flagged" && <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />}
                        {(c.verdict === "partially_true" || c.verdict === "unverified") && (
                          <HelpCircle className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
                        )}
                        <div>
                          <p className="text-sm text-gray-900">{c.claim_text}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                              c.verdict === "verified" ? "bg-green-100 text-green-700" :
                              c.verdict === "disputed" ? "bg-red-100 text-red-700" :
                              c.verdict === "flagged" ? "bg-amber-100 text-amber-700" :
                              "bg-gray-100 text-gray-600"
                            }`}>
                              {c.verdict}
                            </span>
                            <span className="text-xs text-gray-400">{c.claim_type}</span>
                          </div>
                          {c.flag_reason && (
                            <p className="text-xs text-amber-700 mt-1">{c.flag_reason}</p>
                          )}
                          {c.evidence_url && (
                            <a href={c.evidence_url} target="_blank" rel="noreferrer"
                               className="text-xs text-teal-700 hover:underline inline-flex items-center gap-1 mt-1">
                              Evidence <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
}
