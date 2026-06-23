"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Building2, Loader2, CheckCircle, AlertTriangle, XCircle,
  HelpCircle, FileText, ExternalLink, ArrowLeft, ShieldCheck,
  Leaf, Users, Coins, Clock, Info,
} from "lucide-react";
import { useUrlState } from "@/lib/useUrlState";
import { type ViewMode } from "@/lib/plainLanguage";
import SaveButton from "@/components/SaveButton";
import { useToast } from "@/components/Toast";
import ClimateMiniMap from "@/components/ClimateMiniMap";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Phase 7 B3 (2026-05-24) — disclosure-source → compliance-framework mapping.
// Which regulatory disclosure regimes the row demonstrably speaks to. CSRD
// applies whenever Scope 1+2 are disclosed; IFRS S2 whenever SBTi-validation
// or net-zero target is recorded; TCFD whenever scope assurance is present.
function frameworksForDisclosure(d: {
  source?: string;
  scope1_2_verified?: boolean;
  sbti_validated?: boolean;
  net_zero_target_year?: number;
  assurance_level?: string;
}): string[] {
  const out: string[] = [];
  if (d.source === "cdp" || d.source === "sbti") out.push("CSRD");
  if (d.sbti_validated || d.net_zero_target_year) out.push("IFRS S2");
  if (d.scope1_2_verified || d.assurance_level) out.push("TCFD");
  return out;
}

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

// Stage 5 / M6 — per-standard compliance verdict from
// /api/companies/{id} → standards_compliance.
interface StandardCompliance {
  id: string;
  name: string;
  jurisdiction: string;
  status: "aligned" | "partial" | "gap" | "unknown";
  covered_points: string[];
  missing_points: string[];
  evidence_url: string;
}

export default function CompanyDetailPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = params?.ticker;
  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [disclosures, setDisclosures] = useState<Disclosure[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const { showToast } = useToast();
  const [standardsCompliance, setStandardsCompliance] = useState<StandardCompliance[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzeText, setAnalyzeText] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  // F9b — compliance-framework lens: "all" or a single standard id.
  const [complianceLens, setComplianceLens] = useState<string>("all");
  // Polish wave 2 (2026-05-26, deferred #12 UI) — analyze-report URL form
  const [reportUrl, setReportUrl] = useState("");
  const [reportAnalyzing, setReportAnalyzing] = useState(false);
  const [reportResult, setReportResult] = useState<{
    extracted_claims_count: number;
    verdict_summary: Record<string, number>;
    text_length: number;
  } | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  // Phase 7 B3 (2026-05-24) — Business-decision-maker view toggle. Mirrors
  // the Country Passport pattern: ?view=business persists in the URL so a
  // CSO can share a "boardroom view" of a company's disclosure trail.
  const viewSerializer = {
    encode: (v: ViewMode) => (v === "business" ? "business" : null),
    decode: (raw: string | null): ViewMode =>
      raw === "business" ? "business" : "public",
  };
  const [viewMode, setViewMode] = useUrlState<ViewMode>(
    "view",
    "public",
    viewSerializer,
  );

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
        setStandardsCompliance(data.standards_compliance || []);
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
        const v = String(result.verdict || "unverified").replace(/_/g, " ");
        showToast(
          `Claim assessed: ${v}${result.flag_reason ? ` — ${result.flag_reason}` : ""}`,
          result.verdict === "verified" ? "success" : "info",
        );
      } else {
        showToast("Could not verify that claim — please try again.", "error");
      }
    } catch {
      showToast("Network error while verifying the claim.", "error");
    }
    setAnalyzing(false);
  };

  // Polish wave 2 (2026-05-26, deferred #12 UI) — full corporate report
  // analysis: paste a sustainability-report URL, get every claim
  // extracted + graded against the disclosure ledger, persist them
  // all on the company profile in one shot.
  const handleAnalyzeReport = async () => {
    if (!reportUrl.trim() || reportAnalyzing) return;
    setReportAnalyzing(true);
    setReportResult(null);
    setReportError(null);
    try {
      const token =
        typeof window !== "undefined" ? localStorage.getItem("clilens_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(
        `${API_BASE}/api/companies/${ticker}/analyze-report`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ report_url: reportUrl.trim() }),
        }
      );
      if (res.status === 401) {
        setReportError("Sign in to analyse corporate reports.");
        return;
      }
      if (res.status === 422) {
        const body = await res.json().catch(() => ({}));
        setReportError(
          typeof body?.detail === "string"
            ? body.detail
            : "Could not extract usable text from that URL. Try a different report or paste text via /api/research/analyze."
        );
        return;
      }
      if (!res.ok) {
        setReportError(`Report analysis failed (HTTP ${res.status})`);
        return;
      }
      const result = await res.json();
      setReportResult({
        extracted_claims_count: result.extracted_claims_count,
        verdict_summary: result.verdict_summary,
        text_length: result.text_length,
      });
      // Refresh the claims list so the new ones appear in the sidebar.
      try {
        const claimsRes = await fetch(`${API_BASE}/api/companies/${ticker}/claims`);
        if (claimsRes.ok) {
          const data = await claimsRes.json();
          setClaims(data.claims || []);
        }
      } catch {
        // non-fatal
      }
    } catch (e: any) {
      setReportError(e?.message || "Network error");
    } finally {
      setReportAnalyzing(false);
    }
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
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3 flex-wrap">
            {company.name}
            {company.ticker && (
              <span className="text-lg bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono">
                {company.ticker}
              </span>
            )}
            {/* Slice 3 (2026-05-25) — save company to polymorphic
                /api/user/saved (item_type=company). */}
            <SaveButton
              type="company"
              id={company.company_id}
              label={company.name}
              variant="chip"
            />
            {/* chat-as-heart (2026-05-28) — company-detail ask button.
                Pre-fills with company name + ticker so the LLM can
                dispatch verify_corporate_claim / analyze_corporate_report
                with the right parameters. */}
            <button
              type="button"
              onClick={() => {
                window.dispatchEvent(
                  new CustomEvent("climatenews:assistant-prefill", {
                    detail: {
                      prompt: `Tell me about ${company.name}${company.ticker ? ` (${company.ticker})` : ""}'s climate disclosures. What are their net-zero commitments, is SBTi-validated, what should I verify, and how does their reporting compare to peers?`,
                    },
                  }),
                );
              }}
              className="text-sm inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-clilens-teal-50 hover:bg-clilens-teal-100 text-clilens-teal-700 border border-clilens-teal-200 font-normal"
              data-testid="company-ask-assistant"
            >
              Ask about {company.ticker || "this company"}
            </button>
            {/* F9e — discover the compare view from the profile */}
            <Link
              href={`/companies/compare?a=${encodeURIComponent(company.ticker || ticker || "")}&b=`}
              className="text-sm inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white hover:bg-gray-50 text-teal-700 border border-teal-200 font-normal"
            >
              Compare
            </Link>
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
            {viewMode === "business" ? (
              <span
                className={`font-medium ${
                  company.sbti_validated ? "text-teal-700" : "text-amber-700"
                }`}
                data-testid="company-sbti-business"
              >
                {company.sbti_validated
                  ? "SBTi-validated target — ECGT-compliant"
                  : "Not SBTi-validated — net-zero claims carry ECGT Article 4 audit risk"}
              </span>
            ) : (
              <span
                className={`font-medium ${
                  company.sbti_validated ? "text-teal-700" : "text-amber-700"
                }`}
              >
                SBTi: {company.sbti_validated ? "Validated" : "Not validated"}
              </span>
            )}
            {company.net_zero_target_year && (
              <span className="text-gray-600">
                Net-zero target: {company.net_zero_target_year}
              </span>
            )}
          </div>

          {/* Phase 7 B3 (2026-05-24) — Public ↔ Business view toggle. URL-
              persistent via ?view=business so a CSO can share a board-framed
              link. Business view stamps each disclosure with the compliance
              regimes (CSRD / IFRS S2 / TCFD) it speaks to. */}
          <div
            className="mt-5 flex items-center gap-1 p-0.5 bg-gray-100 rounded-md w-fit"
            role="radiogroup"
            aria-label="View mode"
            data-testid="company-view-mode-toggle"
          >
            <button
              type="button"
              role="radio"
              aria-checked={viewMode === "public"}
              onClick={() => setViewMode("public")}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                viewMode === "public"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
              data-testid="company-view-public"
            >
              Public view
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={viewMode === "business"}
              onClick={() => setViewMode("business")}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                viewMode === "business"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
              data-testid="company-view-business"
            >
              Business view
            </button>
          </div>

          {viewMode === "business" && (
            <p
              className="mt-3 text-xs text-gray-600 max-w-2xl"
              data-testid="company-business-context"
            >
              Disclosure trail reframed for fiduciary review. Compliance chips
              below each row show which regimes the data point speaks to
              (CSRD physical-risk, IFRS S2 sustainability, TCFD assurance).
              ECGT Article 4 takes effect 27 Sept 2026 — claims unsupported by
              the disclosure ledger become a board liability after that date.
            </p>
          )}

          {company.country_code && (
            <div className="mt-4">
              <ClimateMiniMap
                countries={[company.country_code]}
                title={`${company.name} — Operating Country`}
                layer="corporate_density"
              />
            </div>
          )}
        </header>

        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            {/* Stage 5 / M6 — per-standard compliance matrix */}
            {standardsCompliance.length > 0 && (
              <section>
                <h2 className="text-xl font-bold text-gray-900 mb-3 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-teal-600" />
                  Compliance against 5 reporting standards
                </h2>
                <p className="text-xs text-gray-600 mb-3">
                  Heuristic assessment of this company&apos;s disclosed data
                  against CSRD, SBTi, TCFD, IFRS S2, and GRI mandatory points.
                </p>
                {/* F9b — lens switcher: view one framework at a time. */}
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {["all", ...standardsCompliance.map((s) => s.id)].map((lens) => (
                    <button
                      key={lens}
                      type="button"
                      onClick={() => setComplianceLens(lens)}
                      className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${complianceLens === lens ? "bg-teal-600 text-white border-teal-600" : "bg-white text-gray-600 border-gray-200 hover:border-teal-400"}`}
                    >
                      {lens === "all" ? "All frameworks" : lens}
                    </button>
                  ))}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-3">
                  {standardsCompliance.filter((s) => complianceLens === "all" || s.id === complianceLens).map((s) => {
                    const color =
                      s.status === "aligned" ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                      : s.status === "partial" ? "bg-amber-50 border-amber-200 text-amber-800"
                      : s.status === "gap" ? "bg-rose-50 border-rose-200 text-rose-800"
                      : "bg-gray-50 border-gray-200 text-gray-600";
                    return (
                      <div key={s.id} className={`border rounded-md px-2.5 py-2 ${color}`}>
                        <div className="text-xs font-semibold">{s.id}</div>
                        <div className="text-[10px] mt-0.5 uppercase tracking-wide">
                          {s.status}
                        </div>
                        <div className="text-[10px] opacity-70 mt-1">
                          {s.covered_points.length}/{s.covered_points.length + s.missing_points.length} points
                        </div>
                      </div>
                    );
                  })}
                </div>
                <details className="text-xs mb-2">
                  <summary className="cursor-pointer text-gray-500 hover:text-gray-700 flex items-center gap-1">
                    <Info className="w-3 h-3" />
                    What do these statuses mean?
                  </summary>
                  <div className="mt-2 p-3 bg-gray-50 rounded-md border border-gray-100 space-y-1.5">
                    <div className="flex items-start gap-1.5">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-emerald-50 text-emerald-800 border border-emerald-200 mt-0.5">Aligned</span>
                      <span className="text-gray-600">This company&apos;s disclosures meet the framework&apos;s core requirements.</span>
                    </div>
                    <div className="flex items-start gap-1.5">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-amber-50 text-amber-800 border border-amber-200 mt-0.5">Partial</span>
                      <span className="text-gray-600">Some elements are addressed but gaps remain.</span>
                    </div>
                    <div className="flex items-start gap-1.5">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-rose-50 text-rose-800 border border-rose-200 mt-0.5">Gap</span>
                      <span className="text-gray-600">No evidence of compliance with this standard was found.</span>
                    </div>
                    <div className="flex items-start gap-1.5">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-gray-100 text-gray-600 border border-gray-200 mt-0.5">Unknown</span>
                      <span className="text-gray-600">Insufficient data to assess compliance.</span>
                    </div>
                  </div>
                </details>
                <details className="text-xs">
                  <summary className="cursor-pointer text-gray-700 hover:text-gray-900 font-medium">
                    Show detailed point-by-point breakdown
                  </summary>
                  <div className="mt-2 space-y-2">
                    {standardsCompliance.filter((s) => complianceLens === "all" || s.id === complianceLens).map((s) => (
                      <div key={s.id} className="bg-white border border-gray-200 rounded-md p-3">
                        <div className="flex items-center justify-between mb-1">
                          <div>
                            <span className="font-semibold text-gray-900">{s.id}</span>
                            <span className="ml-2 text-gray-500">— {s.jurisdiction}</span>
                          </div>
                          <a
                            href={s.evidence_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-teal-700 hover:underline"
                          >
                            source ↗
                          </a>
                        </div>
                        {s.covered_points.length > 0 && (
                          <div className="text-emerald-700">
                            ✓ Covered: {s.covered_points.join(", ")}
                          </div>
                        )}
                        {s.missing_points.length > 0 && (
                          <div className="text-rose-700 mt-1">
                            ✗ Missing: {s.missing_points.join(", ")}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </details>
              </section>
            )}

            {/* F9c — Planet / People / Profit lens. Honest by design: only
                the Planet pillar is populated (CDP/SBTi disclosures are
                emissions-only). People and Profit are explicit "not ingested"
                empty states with the reason, not hollow zeros — matching the
                platform's transparency contract. */}
            {(() => {
              const hasEmissions = disclosures.some(
                (d) =>
                  d.scope1_tco2e != null ||
                  d.scope2_tco2e_market != null ||
                  d.scope2_tco2e_location != null ||
                  d.scope3_tco2e != null
              );
              return (
                <section>
                  <h2 className="text-xl font-bold text-gray-900 mb-1 flex items-center gap-2">
                    <Leaf className="w-5 h-5 text-emerald-600" />
                    Planet · People · Profit
                  </h2>
                  <p className="text-sm text-gray-500 mb-4">
                    A triple-bottom-line view of this company's sustainability,
                    derived from its disclosures. Only the Planet pillar is
                    populated today — the others show why.
                  </p>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Leaf className="w-4 h-4 text-emerald-700" />
                        <span className="font-semibold text-emerald-900">Planet</span>
                      </div>
                      <ul className="text-sm text-emerald-900/90 space-y-1">
                        <li>
                          {hasEmissions
                            ? "✓ Emissions disclosed (Scope 1–3)"
                            : "Emissions not yet disclosed"}
                        </li>
                        <li>
                          {company.sbti_validated
                            ? "✓ SBTi-validated target"
                            : "No SBTi-validated target"}
                        </li>
                        <li>
                          {company.net_zero_target_year
                            ? `✓ Net-zero by ${company.net_zero_target_year}`
                            : "No net-zero target on record"}
                        </li>
                      </ul>
                      <p className="text-xs text-emerald-700/80 mt-2">
                        From CDP / SBTi climate disclosures.
                      </p>
                    </div>

                    <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Users className="w-4 h-4 text-blue-600" />
                        <span className="font-semibold text-blue-900">People</span>
                      </div>
                      <div className="flex items-center gap-1.5 mb-2">
                        <Clock className="w-3.5 h-3.5 text-blue-400" />
                        <span className="text-xs font-medium text-blue-600">Awaiting data ingestion</span>
                      </div>
                      <p className="text-sm text-blue-900/80 mb-2">
                        Social and workforce metrics — once ingested — would display:
                      </p>
                      <ul className="text-sm text-blue-800/70 space-y-1 list-disc pl-4 mb-3">
                        <li>Workforce diversity &amp; inclusion</li>
                        <li>Labour practices &amp; safety records</li>
                        <li>Community impact &amp; human rights</li>
                      </ul>
                      <p className="text-xs text-blue-600/80 mb-2">
                        Requires GRI / CSRD social-disclosure report parsing.
                      </p>
                      <a
                        href="https://www.globalreporting.org/standards/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 underline"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Suggest a data source
                      </a>
                    </div>

                    <div className="rounded-lg border border-violet-200 bg-violet-50/50 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Coins className="w-4 h-4 text-violet-600" />
                        <span className="font-semibold text-violet-900">Profit</span>
                      </div>
                      <div className="flex items-center gap-1.5 mb-2">
                        <Clock className="w-3.5 h-3.5 text-violet-400" />
                        <span className="text-xs font-medium text-violet-600">Awaiting data ingestion</span>
                      </div>
                      <p className="text-sm text-violet-900/80 mb-2">
                        Financial climate alignment — once ingested — would display:
                      </p>
                      <ul className="text-sm text-violet-800/70 space-y-1 list-disc pl-4 mb-3">
                        <li>Green revenue share &amp; taxonomy alignment</li>
                        <li>Fossil fuel exposure &amp; stranded-asset risk</li>
                        <li>ESG-linked financing &amp; sustainable bonds</li>
                      </ul>
                      <p className="text-xs text-violet-600/80 mb-2">
                        Requires annual-report / EU-Taxonomy financial disclosure parsing.
                      </p>
                      <a
                        href="https://ec.europa.eu/sustainable-finance-taxonomy/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 underline"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Suggest a data source
                      </a>
                    </div>
                  </div>
                </section>
              );
            })()}

            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-teal-600" />
                Climate Disclosures
              </h2>
              {disclosures.length === 0 ? (
                <p className="text-sm text-gray-500">No disclosures ingested yet.</p>
              ) : (
                <div className="space-y-3">
                  {disclosures.map((d) => {
                    const frameworks = frameworksForDisclosure(d);
                    return (
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
                      {viewMode === "business" && (
                        <div
                          className="mt-3 pt-3 border-t border-gray-100 space-y-2"
                          data-testid="disclosure-business-footer"
                        >
                          {frameworks.length > 0 && (
                            <div
                              className="flex flex-wrap items-center gap-1.5"
                              data-testid="disclosure-compliance-chips"
                            >
                              <span className="text-[10px] uppercase tracking-wider text-gray-500">
                                Disclosure regime:
                              </span>
                              {frameworks.map((fw) => (
                                <span
                                  key={fw}
                                  className="text-[10px] font-medium px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded"
                                >
                                  {fw}
                                </span>
                              ))}
                            </div>
                          )}
                          {d.offset_based_claims && (
                            <div
                              className="flex items-start gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5"
                              data-testid="disclosure-offset-warning"
                            >
                              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                              <span>
                                <strong>ECGT Article 4 risk:</strong> {d.offset_based_claims}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* F9d — auto drill-down questions derived from the company's own
                data. Tapping one pre-fills the Verify-a-Claim box below. */}
            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-1 flex items-center gap-2">
                Dig deeper
              </h2>
              <p className="text-sm text-gray-600 mb-3">
                Suggested follow-up questions — tap one to verify it against {company.name}&apos;s record.
              </p>
              <div className="flex flex-wrap gap-2 mb-8">
                {(() => {
                  const qs: string[] = [];
                  const n = company.name;
                  if (company.net_zero_target_year) {
                    qs.push(`Is ${n} on track for its ${company.net_zero_target_year} net-zero target?`);
                  } else {
                    qs.push(`Has ${n} committed to a net-zero target year?`);
                  }
                  qs.push(
                    company.sbti_validated
                      ? `Are ${n}'s targets still validated by the Science Based Targets initiative?`
                      : `Why has ${n} not had targets validated by SBTi?`,
                  );
                  qs.push(`How complete is ${n}'s Scope 3 (value-chain) emissions disclosure?`);
                  if (company.sector_nace) {
                    qs.push(`How does ${n} compare to sector peers on decarbonisation?`);
                  }
                  qs.push(`Does ${n} show any signs of greenwashing in its climate claims?`);
                  return qs.map((q, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        setAnalyzeText(q);
                        if (typeof document !== "undefined") {
                          document.getElementById("verify-claim-input")?.scrollIntoView({ behavior: "smooth", block: "center" });
                        }
                      }}
                      className="text-left text-sm px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 hover:bg-teal-600 hover:text-white hover:border-teal-600 transition-colors"
                    >
                      {q}
                    </button>
                  ));
                })()}
              </div>
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
                  id="verify-claim-input"
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

            {/* Polish wave 2 (2026-05-26, deferred audit item #12 UI) —
                full sustainability report analysis. Paste a public report
                URL → extract every claim → grade each against the
                disclosure ledger. methodology_version=corporate_report_v1.0
                distinguishes these in the audit trail. */}
            <section data-testid="analyze-report-section">
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                Analyse a Full Sustainability Report
              </h2>
              <p className="text-sm text-gray-600 mb-3">
                Paste a corporate sustainability or transition-plan report URL
                (HTML or PDF). The platform fetches the text, extracts every
                claim, and grades each against {company.name}'s disclosure
                ledger (ECGT + SBTi + CDP/NZT rules). Heavier than the
                single-claim Verify above — counts against analysis quota.
              </p>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={reportUrl}
                  onChange={(e) => setReportUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAnalyzeReport()}
                  placeholder="https://example.com/sustainability-report-2025.pdf"
                  className="flex-1 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50"
                  disabled={reportAnalyzing}
                  data-testid="analyze-report-url-input"
                />
                <button
                  onClick={handleAnalyzeReport}
                  disabled={!reportUrl.trim() || reportAnalyzing}
                  className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-500 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                  data-testid="analyze-report-submit"
                >
                  {reportAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : "Analyse report"}
                </button>
              </div>
              {reportError && (
                <p className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2" role="alert">
                  {reportError}
                </p>
              )}
              {reportResult && (
                <div className="mt-3 p-3 bg-teal-50 border border-teal-200 rounded text-sm" data-testid="analyze-report-result">
                  <p className="font-medium text-teal-800">
                    {reportResult.extracted_claims_count} claim{reportResult.extracted_claims_count !== 1 ? "s" : ""} extracted from {(reportResult.text_length / 1000).toFixed(1)} KB of report text. New claims appear in the Verified Claims list →
                  </p>
                  {Object.keys(reportResult.verdict_summary).length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {Object.entries(reportResult.verdict_summary).map(([verdict, count]) => (
                        <span
                          key={verdict}
                          className="px-2 py-0.5 text-xs bg-white border border-teal-300 rounded-full"
                        >
                          {verdict}: {count}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
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
