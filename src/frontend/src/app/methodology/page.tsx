"use client";

// Public methodology page (Phase 4 wave 6).
//
// Surfaces the full `/api/methodology/*` bundle — prompts, sustainability
// formula, indicators, calibration metrics, hallucination rates, drift
// verdicts — to anonymous visitors so auditors / journalists / researchers
// can pin a date+commit-aligned methodology snapshot without running a
// deep search first.
//
// Each block is fetched independently so a partial backend outage degrades
// section-by-section instead of blanking the page.

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Brain, FileText, Sliders, Database, Activity, ShieldCheck,
  ShieldAlert, Fingerprint, Route, ExternalLink, GitCommit, Loader2,
  CheckCircle, AlertTriangle, XCircle, HelpCircle,
} from "lucide-react";
import AskAboutButton from "@/components/AskAboutButton";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// --- Types (mirrored from the backend response shapes; loose on purpose so
// the page survives small schema drift) ----------------------------------

interface PromptMeta {
  version: string;
  fingerprint: string;
  description?: string;
  rationale?: string;
  has_system_prompt?: boolean;
  max_tokens?: number;
  temperature?: number;
}

interface FormulaComponent {
  indicator_id: string;
  weight: number;
  description: string;
  normalizer: string;
  normalizer_doc: string;
}

interface ConfidenceBandRow {
  indicators_used: number;
  band_plus_minus: number;
}

interface Indicator {
  indicator_id: string;
  display_name: string;
  unit: string;
  category: string;
  description: string;
  is_higher_better: boolean;
  methodology_url?: string;
}

interface MethodologyBundle {
  git_revision?: string;
  prompts: {
    prompts: Record<string, PromptMeta>;
    total: number;
  };
  sustainability_formula: {
    methodology_version: string;
    methodology_url: string;
    components: FormulaComponent[];
    confidence_band_table: ConfidenceBandRow[];
    scoring_summary: string;
    weight_total: number;
  };
  indicators: {
    indicators: Indicator[];
    available: boolean;
    total_indicators: number;
    coverage_by_indicator: Record<string, number>;
  };
}

interface CalibrationResponse {
  signal: string;
  available: boolean;
  reason?: string;
  metrics?: {
    n_labels: number;
    brier_score?: number;
    ece?: number;
    note?: string;
    // Fit honesty (audit 2026-06-10): these are on the wire but were dropped.
    fit_status?: string;
    margin_of_error?: number | null;
    observed_accuracy?: number;
    stable_fit_min?: number;
  };
}

interface HallucinationRow {
  n: number;
  mean_risk: number;
  high_risk_rate: number;
  extraction_method?: string;
  model_name?: string;
  source_name?: string;
}

interface HallucinationResponse {
  window_days: number;
  available: boolean;
  overall: { n: number; mean_risk: number; high_risk_rate: number };
  by_extraction_method: HallucinationRow[];
  by_model: HallucinationRow[];
  by_source: HallucinationRow[];
  notes?: string[] | null;
}

interface DriftResponse {
  metric: string;
  kl_divergence: number;
  verdict: "stable" | "minor" | "notable" | "significant" | string;
  recent_window_days: number;
  baseline_window_days: number;
  recent_count: number;
  baseline_count: number;
  top_shifts: Array<{
    [key: string]: string | number | undefined;
    recent_share: number;
    baseline_share: number;
    delta: number;
  }>;
  notes?: string | null;
}

interface SelfAuditAxis {
  axis: string;
  score: number;
  status: "measured" | "partial" | "preview" | "insufficient_data" | "unavailable";
  detail: string;
}

interface SelfAuditResponse {
  composite: number;
  max: number;
  axes: SelfAuditAxis[];
  computed_at?: string;
  note?: string;
}

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export default function MethodologyPage() {
  const [bundle, setBundle] = useState<MethodologyBundle | null>(null);
  const [bundleLoading, setBundleLoading] = useState(true);

  const [reliability, setReliability] = useState<CalibrationResponse | null>(null);
  const [agreement, setAgreement] = useState<CalibrationResponse | null>(null);
  const [hallucinationCal, setHallucinationCal] = useState<CalibrationResponse | null>(null);

  const [halRates, setHalRates] = useState<HallucinationResponse | null>(null);
  const [sourceDrift, setSourceDrift] = useState<DriftResponse | null>(null);
  const [promptDrift, setPromptDrift] = useState<DriftResponse | null>(null);
  const [selfAudit, setSelfAudit] = useState<SelfAuditResponse | null>(null);

  useEffect(() => {
    (async () => {
      const b = await fetchJson<MethodologyBundle>("/api/methodology");
      setBundle(b);
      setBundleLoading(false);
    })();

    (async () => {
      const [rel, agr, hal] = await Promise.all([
        fetchJson<CalibrationResponse>("/api/methodology/calibration?signal=reliability_score"),
        fetchJson<CalibrationResponse>("/api/methodology/calibration?signal=agreement_score"),
        fetchJson<CalibrationResponse>("/api/methodology/calibration?signal=hallucination_score"),
      ]);
      setReliability(rel);
      setAgreement(agr);
      setHallucinationCal(hal);
    })();

    (async () => {
      setHalRates(await fetchJson<HallucinationResponse>("/api/methodology/hallucination-rates"));
    })();

    (async () => {
      const [src, prm] = await Promise.all([
        fetchJson<DriftResponse>("/api/drift/source-mix"),
        fetchJson<DriftResponse>("/api/drift/prompt-fingerprints"),
      ]);
      setSourceDrift(src);
      setPromptDrift(prm);
    })();

    // Live self-audit — replaces the hardcoded 3.55 (seq-5b, 2026-06-14).
    (async () => {
      setSelfAudit(await fetchJson<SelfAuditResponse>("/api/methodology/self-audit"));
    })();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold text-clilens-primary">
            Climatefacts.ai
          </Link>
          <nav className="text-sm text-gray-500 flex gap-4">
            <Link href="/about" className="hover:text-gray-800">About</Link>
            <Link href="/methodology" className="text-gray-900 font-medium">Methodology</Link>
            <Link href="/sources" className="hover:text-gray-800">Sources</Link>
          </nav>
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">
        <header>
          <h1 className="text-4xl font-bold text-gray-900 mb-3">Our Methodology</h1>
          <p className="text-lg text-gray-600 max-w-3xl">
            How Climatefacts.ai analyses and scores information, in full.
            Every prompt, formula, indicator, and quality signal the
            platform uses is published below — and the numbers come live
            from the API, so what you see is what the platform is doing
            right now. This page exists so our methodology can be
            objectively reviewed and challenged.
          </p>
          {bundle?.git_revision && (
            <p className="mt-3 text-xs text-gray-500 flex items-center gap-1.5">
              <GitCommit className="w-3.5 h-3.5" />
              Live snapshot pinned to commit{" "}
              <code className="bg-gray-100 px-1.5 py-0.5 rounded font-mono">{bundle.git_revision}</code>
            </p>
          )}
        </header>

        {/* Section: Self-audit — the audit gap ---------------------------------- */}
        <section className="bg-gradient-to-r from-teal-50 to-emerald-50 rounded-xl shadow-sm border border-teal-200 p-6 space-y-5">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2.5">
            <Activity className="w-5 h-5 text-teal-600" />
            Self-audit: where we are vs. where we claim
          </h2>
          <p className="text-sm text-gray-700">
            In May 2026 we commissioned an external analytical audit of
            every component, route, and scoring pipeline. The audit
            re-graded the platform against the same rubric our own
            engineering team uses. The gap between self-claimed and
            audited scores is published here because trust infrastructure
            must model the honesty it asks of others.
          </p>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white/80 rounded-lg border border-teal-100 p-4">
              <div className="text-xs uppercase tracking-wider text-teal-700 font-semibold mb-2">
                Live composite (backend-driven)
              </div>
              <div className="text-3xl font-bold text-teal-600">
                {selfAudit?.composite != null ? (
                  <>{selfAudit.composite}<span className="text-lg text-teal-400">/5</span></>
                ) : (
                  <span className="text-2xl text-teal-400">Loading…</span>
                )}
              </div>
              <div className="text-xs text-teal-700 mt-1">
                {selfAudit?.computed_at ? (
                  <>Computed {new Date(selfAudit.computed_at).toLocaleString()} &middot; {selfAudit.axes.length} axes</>
                ) : (
                  "Live composite from calibration, source tiers, embeddings, coverage, and provenance data"
                )}
              </div>
            </div>
            <div className="bg-white/80 rounded-lg border border-amber-100 p-4">
              <div className="text-xs uppercase tracking-wider text-amber-700 font-semibold mb-2">Last audited (End2End, 2026-05-27)</div>
              <div className="text-3xl font-bold text-amber-600">3.55<span className="text-lg text-amber-400">/5</span></div>
              <div className="text-xs text-amber-700 mt-1">
                Same rubric, applied by audit against live code + data. Up from 3.05 (2026-05-26).
                The live composite (left) now drives from backend data — it replaces the
                previously hardcoded 4.78 self-claim.
              </div>
            </div>
          </div>

          {/* Live axes breakdown */}
          {selfAudit?.axes && selfAudit.axes.length > 0 && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 text-xs mt-4">
              {selfAudit.axes.map((axis) => (
                <div
                  key={axis.axis}
                  className="bg-white/80 rounded border border-gray-200 p-2 flex justify-between items-start"
                >
                  <div>
                    <div className="font-medium text-gray-900 capitalize">
                      {axis.axis.replace(/_/g, " ")}
                    </div>
                    <div className="text-gray-500">{axis.detail}</div>
                  </div>
                  <div className="flex items-center gap-1.5 ml-2 shrink-0">
                    <span className="font-mono text-sm font-bold text-gray-800">
                      {axis.score}
                    </span>
                    <span className="text-gray-400">/5</span>
                    {axis.status === "insufficient_data" || axis.status === "unavailable" ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                    ) : axis.status === "preview" || axis.status === "partial" ? (
                      <HelpCircle className="w-3.5 h-3.5 text-blue-500" />
                    ) : (
                      <CheckCircle className="w-3.5 h-3.5 text-teal-500" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div>
            <h3 className="font-semibold text-gray-900 text-sm mb-2">What the audit found</h3>
            <div className="grid sm:grid-cols-2 gap-2 text-xs">
              {[
                { axis: "Reliability Tiering", before: "4.4-4.8", after: "3.5 → 4.6 (2026-05-26)", fix: "✅ DB-backed source credibility tiers + 3-axis (editorial/factcheck/transparency) wired into compute_weighted_score. Mig 045 fence guarantees no NULL axes." },
                { axis: "Calibration Math", before: "4.6-4.7", after: "2.8 → 3.4 (2026-05-27)", fix: "✅ Calibration fence — min_labels=50, sub-threshold fits stamped 'preview' (commit 5dc7b12). Awaiting label volume." },
                { axis: "Hallucination Detection", before: "4.8", after: "3.2 → 4.3 (2026-05-27)", fix: "✅ spaCy NER model now downloaded in API Dockerfile so PERSON/ORG/GPE/LOC entity grounding runs in prod (was regex-fallback)." },
                { axis: "Sustainability Composite", before: "4.8", after: "3.3", fix: "Integrate ND-GAIN; widen confidence band on mixed-year inputs. Pending." },
                { axis: "Claim Density Honesty", before: "4.6", after: "4.6 → 4.8 (2026-05-25)", fix: "✅ Claim-density factor + Limited Evidence badge — '90% credibility with 1 claim' no longer possible." },
                { axis: "Deep Search Relevance", before: "—", after: "3.8 → 4.5 (2026-05-25)", fix: "✅ Min semantic similarity 0.55 + tightened overlap guardrail (0.25). Fixed Slovenian-noise-for-India-query trust bug." },
                { axis: "Multi-claim Extraction Yield", before: "—", after: "2.2 claims/article → target 3-8 (2026-05-27)", fix: "✅ Prompt v1.1 explicitly targets 3-8 claims (was 'up to N'). Primary DeepSeek extractor now uses the registered prompt template — previously diverged from secondary Anthropic." },
                { axis: "External Citation Credibility", before: "—", after: "n/a → 4.5 (2026-05-27)", fix: "✅ Perplexity deep-search citations now annotated with tier + 0-100 credibility score via source_credibility_tiers lookup." },
                { axis: "Source Stamping at Ingest", before: "—", after: "0% → 100% (2026-05-27)", fix: "✅ New article ingest stamps articles.source_credibility_score via source_tier_service (was hardcoded 50 / NULL across the corpus)." },
                { axis: "Bias Auditor", before: "—", after: "missing → 4.5 (2026-05-27)", fix: "✅ Chi-squared bias auditor live at /api/methodology/bias-audit — Cramér's V + critical-value gate at α=0.05 (commit 5dc7b12)." },
                { axis: "Provenance Ledger", before: "—", after: "empty → backfilled (2026-05-27)", fix: "✅ Article-enrichment path now writes claim_provenance for every LLM call (commit 5dc7b12)." },
                { axis: "Premium Gating", before: "—", after: "ungated → Standard+ (2026-05-27)", fix: "✅ /companies/{ticker}/analyze-report + /research/upload now require Standard+ subscription (document_ingestion premium feature)." },
              ].map((row) => (
                <div key={row.axis} className="bg-white/80 rounded border border-gray-200 p-3">
                  <div className="font-medium text-gray-900">{row.axis}</div>
                  <div className="mt-1 flex gap-2 items-baseline">
                    <span className="text-teal-700">Claimed: {row.before}</span>
                    <span className="text-gray-300">→</span>
                    <span className="text-amber-700 font-medium">Audited: {row.after}</span>
                  </div>
                  <div className="text-gray-500 mt-1">{row.fix}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-sm text-gray-600 bg-white/80 rounded border border-gray-200 p-3">
            <strong className="text-gray-900">Last audited composite (2026-05-27):</strong> ~3.55/5
            by the End2End audit, up from 3.05 the day before. That wave closed
            the three biggest residual gaps: multi-claim extraction yield
            (prompt v1.1 targets 3-8 instead of "up to N"), spaCy NER entity
            grounding (now downloaded in the API Dockerfile rather than silently
            degrading to regex), and external citation credibility (Perplexity
            URLs annotated with tier). Trust work has continued since — see the
            "Since the audit" card below — but those gains are not yet reflected
            in a re-graded score, so the audited figure stands until the next
            audit. Calibration label volume + ND-GAIN integration + full
            transition-risk scoring remain the highest-leverage open items — see{" "}
            <a
              href="https://github.com/eljaplacido/climatefactsai/blob/main/docs/improvementplans/End2End-Audit-Benchmark-2026-05-27.md"
              target="_blank" rel="noreferrer"
              className="text-teal-700 hover:underline"
            >
              End2End Audit Benchmark 2026-05-27 <ExternalLink className="inline w-3 h-3" />
            </a>{" "}
            for the file-level evidence per fix.
          </div>

          <p className="text-xs text-gray-500 italic border-t border-teal-200 pt-3">
            Publishing this gap is our strongest trust signal. It inverts
            every greenwashing pattern: we show the gap, we name the fixes, and
            we give a date by which we commit to closing it. This page will be
            updated as each axis improves.
          </p>
        </section>

        {/* Section: Recent platform updates -------------------------------- */}
        <section
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4"
          data-testid="methodology-recent-updates"
        >
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2.5">
            <Activity className="w-5 h-5 text-emerald-600" />
            Recent platform updates (May – June 2026)
          </h2>
          <p className="text-sm text-gray-700">
            The 2026-05-27 audit wave closed the Honest-Gap-Audit v2 plus the
            End2End audit's Section I priority list — multi-claim yield, entity
            grounding NER, external citation credibility, source stamping at
            ingest, and premium gating on heavy LLM endpoints. Work has
            continued since: the <strong>Since the audit</strong> card below
            lists what shipped through 2026-06-08 (semantic-search embeddings,
            source-health monitoring, the credibility-tier completion, drift
            honesty) — ahead of the next re-score. Every change has file-level
            evidence in git + corresponding tests.
          </p>
          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            {[
              {
                area: "Since the audit (May 28 – Jun 8, 2026)",
                items: [
                  "Semantic search resurrected — GX10 bge-m3 embedding write path (the corpus was ~0/666 embedded)",
                  "Source-health canary — daily feed probe; a feed auto-disables after 5 consecutive failures",
                  "Credibility tiers completed — a migration version-prefix collision had silently dropped ~55 climate-journalism tier seeds; fixed (mig 066). source_credibility_tiers now 164 rows in prod",
                  "Drift detector honesty — thin windows report 'insufficient_data' (neutral) instead of a fake-green 'stable'",
                  "SBTi validated-target detection fixed — 9 → ~3,900 companies",
                  "Company head-to-head compare — size-independent ambition leader; comparisons are now saveable",
                  "LLM cost telemetry — cloud-vs-GX10 spend is now visible",
                  "Billing / subscription routes aligned to the DB schema (paid paths were 500-ing)",
                ],
              },
              {
                area: "Truth-engine scoring",
                items: [
                  "Claim-density factor (Slice 4a) — 1/1 verified no longer = 8/8 verified",
                  "Limited Evidence badge below 3 claims",
                  "3-axis source scoring (editorial / factcheck / transparency) wired into credibility math (Polish wave 2)",
                  "Multi-claim extraction prompt v1.1 — targets 3-8 claims explicitly (was 'up to N'; lifted from 2.2 avg)",
                  "DeepSeek primary extractor now uses the registered prompt template (parity with Anthropic secondary)",
                  "spaCy NER model downloaded in API Dockerfile — entity grounding runs at semantic level, not regex fallback",
                  "Ingest stamps articles.source_credibility_score via tier service (was hardcoded 50 across whole corpus)",
                  "External Perplexity citations annotated with tier + credibility score chip",
                ],
              },
              {
                area: "Retrieval honesty",
                items: [
                  "Deep-search min semantic similarity 0.55 + min FTS rank 0.01",
                  "Relevance guardrail tightened — overlap ≥ 0.25 OR rel ≥ 0.5",
                  "Full-text fetch pre-pass before claim extraction (Slice 4b)",
                  "Link-rot detection — nightly HEAD probe (Slice 5a + Mig 046)",
                ],
              },
              {
                area: "Save & explore",
                items: [
                  "Polymorphic /api/user/saved — 8 item types (Slice 3)",
                  "My Saves page surfaces everything",
                  "Scenario explorer — IPCC AR6 interpolation with 'not simulation' disclaimer",
                ],
              },
              {
                area: "Document analysis",
                items: [
                  "/api/research/upload — PDF / DOCX / TXT up to 25 MiB (Deferred #11)",
                  "/api/companies/{ticker}/analyze-report — full sustainability report → claims (Deferred #12)",
                  "Research feed — subscribe-to-topic + CrossRef poller (Deferred #13)",
                ],
              },
              {
                area: "Agentic chat",
                items: [
                  "15 single-sourced agentic skills (was 11) — backend ↔ frontend pin tests guarantee parity",
                  "save_item / subscribe_research_topic / explore_scenario / analyze_corporate_report added",
                  "Deep-search inline follow-up chat (Slice 6)",
                ],
              },
              {
                area: "Infrastructure",
                items: [
                  "Local GX10 LLM routing — flip CLILENS_ENRICHMENT_PROVIDER=local-gx10 once hardware serves",
                  "Auto-fallback to DeepSeek if GX10 unreachable",
                  "Cloud Scheduler crons: cn-link-check + cn-research-poll + cn-aoi-poll provisioned (mig 046 + 047)",
                  "Migration runner @notolerate directive — broken migrations now fail loud",
                  "claim_provenance ledger now written from article enrichment path (was empty in prod)",
                  "Chi-squared bias auditor live at /api/methodology/bias-audit — Cramér's V + critical-value gate at α=0.05",
                  "Calibration refit default min_labels bumped 5→50 — production-grade Platt fits only",
                  "Admin endpoints (link-check, research-poll) accept SCHEDULER_SECRET as fallback header for Cloud Scheduler",
                  "Premium gating on /companies/{ticker}/analyze-report + /research/upload — Standard+ document_ingestion feature",
                ],
              },
              {
                area: "Persona surfaces",
                items: [
                  "Dashboard — Persona Lens (6 personas) + Analytics & Exports tile",
                  "Map country panel — 3-axis chips per source (editorial / factcheck / transparency)",
                  "SourceProfileCard — numeric 0-100 scores per axis below qualitative labels",
                  "Export tiles wired to logged-in saves (articles / companies / countries / searches)",
                ],
              },
            ].map((card) => (
              <div
                key={card.area}
                className="bg-gradient-to-br from-gray-50 to-white border border-gray-200 rounded-lg p-3"
              >
                <h4 className="text-xs uppercase tracking-wider text-emerald-700 font-semibold mb-2">
                  {card.area}
                </h4>
                <ul className="space-y-1 text-xs text-gray-700">
                  {card.items.map((it) => (
                    <li key={it} className="flex gap-1.5">
                      <CheckCircle className="w-3 h-3 text-emerald-600 flex-shrink-0 mt-0.5" />
                      <span>{it}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-500 italic border-t border-gray-200 pt-3">
            Full commit ledger in{" "}
            <a
              href="https://github.com/eljaplacido/climatefactsai/blob/main/docs/improvementplans/"
              target="_blank" rel="noreferrer"
              className="text-teal-700 hover:underline"
            >
              docs/improvementplans/ <ExternalLink className="inline w-3 h-3" />
            </a>
            . Each item also has corresponding pytest coverage in tests/backend/
            and tests/scripts/.
          </p>
        </section>

        {/* Section: How verification works (narrative) ------------------- */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            How verification works
            <AskAboutButton
              prompt="Explain the 5-stage verification pipeline in plain language — what does each stage check, and how do they combine into the final credibility score I see on articles?"
              ariaLabel="Ask the assistant: explain the verification pipeline"
            />
          </h2>
          <p className="text-sm text-gray-700">
            Every URL the platform analyses runs through five stages. Each
            stage emits a versioned audit record so a displayed score can
            be traced back to the exact prompt, model, retrieval strategy,
            and source articles that produced it.
          </p>

          <ol className="space-y-3">
            <ProcessStep n={1} title="Article ingestion & extraction"
              body="Title, author, publish date, source, language, and full body are extracted. The fetcher validates URLs against SSRF blocklists and re-validates after every redirect hop." />
            <ProcessStep n={2} title="Claim extraction"
              body="A versioned LLM prompt identifies factual claims. The prompt name + version + content-fingerprint are recorded on every output (see Models & Prompts below)." />
            <ProcessStep n={3} title="Evidence retrieval"
              body="Hybrid retrieval combines internal corpus (FTS + HNSW vector search + knowledge graph), external web search via Perplexity (when configured), and weather context. Retrieval strategy is recorded per call." />
            <ProcessStep n={4} title="Multi-LLM verification"
              body="The primary model's claims are cross-checked against a secondary LLM. Token-level Jaccard similarity yields an agreement score; large disagreements downgrade confidence." />
            <ProcessStep n={5} title="Hallucination grounding"
              body="A separate hallucination check compares the synthesised answer against the retrieved articles. Entity overlap + statistic verification + LLM grounding feed into the final risk score, which is calibrated against ground-truth labels." />
          </ol>

          <div className="grid md:grid-cols-2 gap-3 pt-3">
            <div className="bg-green-50 border border-green-200 rounded p-3 text-sm">
              <div className="flex items-center gap-2 font-semibold text-green-900">
                <CheckCircle className="w-4 h-4" /> What we surface
              </div>
              <ul className="list-disc list-inside text-xs text-green-800 mt-1 space-y-0.5">
                <li>Versioned prompt + fingerprint per LLM call</li>
                <li>Source articles that fed each output</li>
                <li>Reliability + agreement + hallucination scores</li>
                <li>Calibration metrics tied to reviewer labels</li>
                <li>Drift verdicts on source mix and prompts</li>
              </ul>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-sm">
              <div className="flex items-center gap-2 font-semibold text-yellow-900">
                <AlertTriangle className="w-4 h-4" /> Known limits
              </div>
              <ul className="list-disc list-inside text-xs text-yellow-800 mt-1 space-y-0.5">
                <li>LLMs occasionally misread subtle scientific nuance</li>
                <li>Calibration requires labelled reviews to accumulate</li>
                <li>Paywalled sources are not retrievable</li>
                <li>Predictive claims are flagged but not adjudicated</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Section: Prompts ----------------------------------------------- */}
        <Section
          icon={<Brain className="w-5 h-5 text-teal-600" />}
          title="Models & versioned prompts"
          intro="Every LLM call goes through a registered, fingerprinted prompt. The fingerprint is a SHA-256 prefix of template + system content; two prompts with the same fingerprint are byte-identical. Drift detection (below) watches the distribution of these fingerprints over time."
        >
          {bundleLoading ? (
            <Loading />
          ) : bundle ? (
            <PromptsTable prompts={bundle.prompts.prompts} />
          ) : (
            <Unavailable reason="methodology bundle could not be loaded" />
          )}
        </Section>

        {/* Section: Sustainability formula -------------------------------- */}
        <Section
          icon={<Sliders className="w-5 h-5 text-teal-600" />}
          title="Sustainability score formula"
          intro="Country sustainability scores are a weighted combination of Bayesian-normalised indicators. Weights of missing components redistribute across the available subset; the confidence band widens when fewer indicators contribute."
        >
          {bundleLoading ? (
            <Loading />
          ) : bundle ? (
            <FormulaBlock formula={bundle.sustainability_formula} />
          ) : (
            <Unavailable reason="formula could not be loaded" />
          )}
        </Section>

        {/* Section: Indicators -------------------------------------------- */}
        <Section
          icon={<Database className="w-5 h-5 text-teal-600" />}
          title="Indicator catalogue"
          intro="Every climate indicator the platform stores, with its authoritative source. Indicators flow into country_indicators from per-source adapters (Climate TRACE, Our World in Data, Climate Action Tracker) and feed the sustainability formula above."
        >
          {bundleLoading ? (
            <Loading />
          ) : bundle?.indicators?.available ? (
            <IndicatorsTable
              indicators={bundle.indicators.indicators}
              coverage={bundle.indicators.coverage_by_indicator}
            />
          ) : (
            <Unavailable reason="indicator catalogue is empty — adapters may not have run yet" />
          )}
        </Section>

        {/* Section: Calibration ------------------------------------------- */}
        <Section
          icon={<Activity className="w-5 h-5 text-teal-600" />}
          title="Calibration"
          intro="Brier score, Expected Calibration Error, and Platt scaling for each calibratable signal. A well-calibrated system has Brier ≈ 0 and ECE close to 0. When labels are sparse, the metrics show 'awaiting reviews' — calibration data accumulates as reviewers grade analyses."
        >
          <div className="grid md:grid-cols-3 gap-4">
            <CalibrationCard signal="Reliability" data={reliability} />
            <CalibrationCard signal="Agreement" data={agreement} />
            <CalibrationCard signal="Hallucination" data={hallucinationCal} />
          </div>
        </Section>

        {/* Section: Hallucination rates ----------------------------------- */}
        <Section
          icon={<ShieldCheck className="w-5 h-5 text-teal-600" />}
          title="Hallucination rates"
          intro="Per-extraction-method, per-model, and per-source hallucination scores over the last 30 days. Each LLM output is checked against its retrieved sources; the resulting risk score is recorded in claim_provenance and aggregated here."
        >
          <HallucinationBlock data={halRates} />
        </Section>

        {/* Section: Drift detection --------------------------------------- */}
        <Section
          icon={<Route className="w-5 h-5 text-teal-600" />}
          title="Drift detection"
          intro="KL-divergence between the recent 7-day window and the prior 30-day baseline, computed independently for the article source mix and the prompt-fingerprint distribution. A 'significant' verdict signals a meaningful shift — operators investigate."
        >
          <div className="grid md:grid-cols-2 gap-4">
            <DriftCard label="Article source mix" data={sourceDrift} keyField="source_name" />
            <DriftCard label="Prompt fingerprints" data={promptDrift} keyField="prompt_fingerprint" />
          </div>
        </Section>

        {/* Section: Verdict glossary -------------------------------------- */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-3">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            Verdict labels
            <AskAboutButton
              prompt="Explain what each verdict label means — verified, partially_true, disputed, unverified, etc. — and how the platform decides between them. What evidence threshold flips a claim from one to another?"
              ariaLabel="Ask the assistant: explain verdict labels"
            />
          </h2>
          <p className="text-sm text-gray-700">
            How the platform classifies an analysed claim once evidence is gathered.
          </p>
          <div className="grid sm:grid-cols-2 gap-2">
            <VerdictRow icon={<CheckCircle className="w-4 h-4 text-green-600" />}
              label="Verified"
              tone="bg-green-50 border-green-200 text-green-900"
              description="Multiple credible sources confirm with high confidence." />
            <VerdictRow icon={<AlertTriangle className="w-4 h-4 text-yellow-600" />}
              label="Partially true"
              tone="bg-yellow-50 border-yellow-200 text-yellow-900"
              description="Some evidence supports, some contradicts, or context is needed." />
            <VerdictRow icon={<XCircle className="w-4 h-4 text-red-600" />}
              label="Disputed / false"
              tone="bg-red-50 border-red-200 text-red-900"
              description="Scientific consensus contradicts the claim." />
            <VerdictRow icon={<HelpCircle className="w-4 h-4 text-gray-600" />}
              label="Unverified"
              tone="bg-gray-50 border-gray-200 text-gray-900"
              description="Insufficient evidence to make a determination." />
          </div>
        </section>

        {/* Section: Feedback ---------------------------------------------- */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-3">
          <h2 className="text-2xl font-bold text-gray-900">Feedback & corrections</h2>
          <p className="text-sm text-gray-700">
            We want this methodology to be challenged. If you spot a
            weakness in a prompt, disagree with an indicator weight, find
            a calibration label we got wrong, or have a primary source
            you think we should add — tell us, and we'll respond.
          </p>
          <div className="grid sm:grid-cols-3 gap-3 text-sm">
            <a
              href="mailto:methodology@climatefacts.ai?subject=Methodology%20feedback"
              className="block bg-teal-50 border border-teal-200 rounded p-3 hover:bg-teal-100"
            >
              <div className="font-semibold text-teal-900">Methodology suggestions</div>
              <div className="text-xs text-teal-800">
                methodology@climatefacts.ai
              </div>
            </a>
            <a
              href="mailto:corrections@climatefacts.ai?subject=Correction%20request"
              className="block bg-amber-50 border border-amber-200 rounded p-3 hover:bg-amber-100"
            >
              <div className="font-semibold text-amber-900">Corrections</div>
              <div className="text-xs text-amber-800">
                corrections@climatefacts.ai
              </div>
            </a>
            <a
              href="mailto:research@climatefacts.ai?subject=New%20data%20source"
              className="block bg-emerald-50 border border-emerald-200 rounded p-3 hover:bg-emerald-100"
            >
              <div className="font-semibold text-emerald-900">New data sources</div>
              <div className="text-xs text-emerald-800">
                research@climatefacts.ai
              </div>
            </a>
          </div>
          <p className="text-xs text-gray-500 pt-1">
            Reviewer-graded calibration labels can also be submitted by
            authorised partners via{" "}
            <code className="bg-gray-100 px-1 py-0.5 rounded font-mono">
              POST /api/methodology/calibration/labels
            </code>{" "}
            — contact us for credentials.
          </p>
        </section>

        {/* Section: Compliance ------------------------------------------- */}
        <Section
          icon={<FileText className="w-5 h-5 text-teal-600" />}
          title="Privacy, terms & GDPR"
          intro="Required reading for EU users and enterprise customers. The full documents are version-controlled in the repository; older versions remain reachable by git SHA."
        >
          <ul className="space-y-2 text-sm">
            <DocLink href="https://github.com/eljaplacido/climatenews/blob/main/docs/compliance/PRIVACY_POLICY.md"
                     label="Privacy Policy"
                     description="What we collect, why, who we share with, your rights" />
            <DocLink href="https://github.com/eljaplacido/climatenews/blob/main/docs/compliance/TERMS_OF_SERVICE.md"
                     label="Terms of Service"
                     description="The contract between the platform and you" />
            <DocLink href="https://github.com/eljaplacido/climatenews/blob/main/docs/compliance/GDPR_DPIA.md"
                     label="GDPR DPIA"
                     description="Article 35 Data Protection Impact Assessment" />
            <DocLink href="https://github.com/eljaplacido/climatenews/blob/main/docs/compliance/DATA_PROCESSING.md"
                     label="Sub-processor inventory"
                     description="Every third party that touches user data" />
          </ul>
        </Section>

        {/* Phase 7 B3 (2026-05-24) — Corporate-claim verification surface. */}
        <Section
          icon={<ShieldCheck className="w-5 h-5 text-teal-600" />}
          title="Corporate climate claim verification"
          intro="The /companies surface verifies corporate climate claims against the public disclosure ledger (CDP / SBTi / Net Zero Tracker). Verdicts are deterministic and unit-tested — no LLM is in the verdict path."
        >
          <div id="corporate-verification" className="space-y-3 text-sm text-gray-700">
            <p>
              Each claim is routed through a rule set pinned by{" "}
              <code className="bg-gray-100 px-1 py-0.5 rounded font-mono text-xs">
                tests/api/test_company_routes.py
              </code>
              . The taxonomy is fixed:
            </p>
            <ul className="list-disc list-inside space-y-1 text-xs">
              <li>
                <strong>flagged</strong> — offset-based "climate neutral"
                phrasings (ECGT Article 4 prohibition, effective 27 Sept 2026)
              </li>
              <li>
                <strong>verified</strong> — net-zero claims supported by SBTi
                validation in the company's disclosure context
              </li>
              <li>
                <strong>disputed</strong> — net-zero claims without SBTi
                evidence (fail-safe default: absent confirmation → disputed)
              </li>
              <li>
                <strong>partially_true</strong> — emissions-reduction claims
                that require cross-referencing the Scope 1/2/3 rows on the
                company's profile
              </li>
              <li>
                <strong>unverified</strong> — claims that don't match a
                routing rule (fallback bucket)
              </li>
            </ul>
            <p className="text-xs text-gray-600 italic">
              Seed data covers ~17 well-known public companies across tech,
              consumer goods, industrials, and oil & gas — illustrative of
              both SBTi-validated and unvalidated cohorts. Once the CDP / SBTi
              / NZT adapters run, fresher data idempotently overwrites the
              seed rows.
            </p>
          </div>
        </Section>

        <footer className="text-xs text-gray-500 pt-6 border-t border-gray-200">
          Methodology snapshot generated live from{" "}
          <code className="bg-gray-100 px-1.5 py-0.5 rounded font-mono">GET /api/methodology</code>{" "}
          and related endpoints. To pin a snapshot for audit, request the
          bundle directly and attach the response to your record.
        </footer>
      </main>
    </div>
  );
}

// --- Building blocks ------------------------------------------------------

function Section({
  icon, title, intro, children,
}: {
  icon: React.ReactNode;
  title: string;
  intro: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
      <header>
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2.5">
          {icon}
          {title}
        </h2>
        <p className="text-sm text-gray-600 mt-1 max-w-3xl">{intro}</p>
      </header>
      {children}
    </section>
  );
}

function ProcessStep({ n, title, body }: { n: number; title: string; body: string }) {
  return (
    <li className="flex gap-3">
      <span className="flex-shrink-0 w-7 h-7 rounded-full bg-teal-100 text-teal-700 font-semibold text-sm flex items-center justify-center">
        {n}
      </span>
      <div>
        <h3 className="font-semibold text-gray-900 text-sm">{title}</h3>
        <p className="text-sm text-gray-700">{body}</p>
      </div>
    </li>
  );
}

function VerdictRow({
  icon, label, description, tone,
}: { icon: React.ReactNode; label: string; description: string; tone: string }) {
  return (
    <div className={`border rounded p-3 text-sm flex items-start gap-2 ${tone}`}>
      {icon}
      <div>
        <div className="font-semibold">{label}</div>
        <div className="text-xs opacity-90">{description}</div>
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
      <Loader2 className="w-4 h-4 animate-spin" />
      Loading…
    </div>
  );
}

function Unavailable({ reason }: { reason: string }) {
  return (
    <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
      Unavailable — {reason}.
    </div>
  );
}

function PromptsTable({ prompts }: { prompts: Record<string, PromptMeta> }) {
  const entries = Object.entries(prompts);
  if (entries.length === 0) return <Unavailable reason="no prompts registered" />;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
            <th className="py-2 pr-3">Name</th>
            <th className="py-2 pr-3">Version</th>
            <th className="py-2 pr-3">Fingerprint</th>
            <th className="py-2 pr-3">Description</th>
            <th className="py-2 pr-3">Why</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, meta]) => (
            <tr key={name} className="border-b border-gray-100 align-top">
              <td className="py-2 pr-3 font-mono text-gray-900">{name}</td>
              <td className="py-2 pr-3 font-mono text-teal-700">{meta.version}</td>
              <td className="py-2 pr-3 font-mono text-xs text-gray-500" title={meta.fingerprint}>
                <span className="inline-flex items-center gap-1">
                  <Fingerprint className="w-3 h-3" />
                  {meta.fingerprint}
                </span>
              </td>
              <td className="py-2 pr-3 text-gray-700 max-w-md">{meta.description || "—"}</td>
              <td className="py-2 pr-3 text-gray-600 max-w-md text-xs">{meta.rationale || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FormulaBlock({ formula }: { formula: MethodologyBundle["sustainability_formula"] }) {
  const weightTotalPct = Math.round(formula.weight_total * 100);
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-700">{formula.scoring_summary}</p>
      <div className="text-xs text-gray-500">
        Methodology version:{" "}
        <code className="bg-gray-100 px-1 py-0.5 rounded font-mono">{formula.methodology_version}</code>
        {formula.methodology_url && (
          <>
            {" · "}
            <a className="text-teal-700 hover:underline" href={formula.methodology_url} target="_blank" rel="noreferrer">
              Detailed methodology <ExternalLink className="inline w-3 h-3" />
            </a>
          </>
        )}
        {" · "}weights sum to {weightTotalPct}%
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
              <th className="py-2 pr-3">Indicator</th>
              <th className="py-2 pr-3">Weight</th>
              <th className="py-2 pr-3">Description</th>
              <th className="py-2 pr-3">Normalizer</th>
            </tr>
          </thead>
          <tbody>
            {formula.components.map((c) => (
              <tr key={c.indicator_id} className="border-b border-gray-100 align-top">
                <td className="py-2 pr-3 font-mono text-gray-900">{c.indicator_id}</td>
                <td className="py-2 pr-3 font-medium text-teal-700">{Math.round(c.weight * 100)}%</td>
                <td className="py-2 pr-3 text-gray-700">{c.description}</td>
                <td className="py-2 pr-3 text-xs text-gray-600">
                  <code className="bg-gray-100 px-1 py-0.5 rounded font-mono mr-1">{c.normalizer}</code>
                  {c.normalizer_doc}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-1">Confidence bands</h4>
        <div className="flex flex-wrap gap-2 text-xs">
          {formula.confidence_band_table.map((row) => (
            <div key={row.indicators_used} className="bg-gray-100 rounded px-2 py-1">
              <span className="text-gray-500">{row.indicators_used} indicators →</span>{" "}
              <span className="font-mono text-gray-900">±{row.band_plus_minus}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function IndicatorsTable({
  indicators, coverage,
}: { indicators: Indicator[]; coverage: Record<string, number> }) {
  if (indicators.length === 0) return <Unavailable reason="no indicators defined" />;

  const byCategory = indicators.reduce<Record<string, Indicator[]>>((acc, i) => {
    (acc[i.category] = acc[i.category] || []).push(i);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {Object.entries(byCategory).map(([category, items]) => (
        <div key={category}>
          <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-1">{category}</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b border-gray-200">
                  <th className="py-1.5 pr-3">Indicator</th>
                  <th className="py-1.5 pr-3">Unit</th>
                  <th className="py-1.5 pr-3">Direction</th>
                  <th className="py-1.5 pr-3">Countries</th>
                  <th className="py-1.5 pr-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.indicator_id} className="border-b border-gray-100">
                    <td className="py-1.5 pr-3">
                      <div className="font-mono text-gray-900">{i.indicator_id}</div>
                      <div className="text-xs text-gray-500">{i.display_name}</div>
                    </td>
                    <td className="py-1.5 pr-3 text-gray-700">{i.unit}</td>
                    <td className="py-1.5 pr-3 text-xs">
                      {i.is_higher_better ? (
                        <span className="text-teal-700">higher is better</span>
                      ) : (
                        <span className="text-orange-700">lower is better</span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 text-gray-700">
                      {coverage[i.indicator_id] ?? "—"}
                    </td>
                    <td className="py-1.5 pr-3">
                      {i.methodology_url ? (
                        <a className="text-teal-700 hover:underline text-xs" href={i.methodology_url} target="_blank" rel="noreferrer">
                          methodology <ExternalLink className="inline w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

function CalibrationCard({ signal, data }: { signal: string; data: CalibrationResponse | null }) {
  if (data === null) {
    return (
      <div className="border border-gray-200 rounded-lg p-4">
        <Loading />
      </div>
    );
  }
  if (!data.available) {
    return (
      <div className="border border-gray-200 rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">{signal}</h3>
        <p className="text-xs text-amber-700">Unavailable: {data.reason || "no data"}</p>
      </div>
    );
  }
  const m = data.metrics;
  if (!m || (m.n_labels ?? 0) === 0) {
    return (
      <div className="border border-gray-200 rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">{signal}</h3>
        <p className="text-xs text-gray-500">
          Awaiting reviewer labels — calibration accumulates as analyses are graded.
        </p>
      </div>
    );
  }
  // Fit honesty badge — a Platt fit below the production threshold is a
  // "preview" that the platform does NOT apply at inference (audit 2026-06-10).
  const fitStatus = m.fit_status || "";
  const fitBadge: Record<string, { label: string; cls: string }> = {
    stable: { label: "Stable fit", cls: "bg-green-100 text-green-800" },
    preview: { label: "Preview fit", cls: "bg-amber-100 text-amber-800" },
    insufficient_data: { label: "Insufficient data", cls: "bg-gray-100 text-gray-700" },
    no_labels: { label: "No labels", cls: "bg-gray-100 text-gray-500" },
  };
  const badge = fitBadge[fitStatus];
  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-1">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold text-gray-900">{signal}</h3>
        {badge && (
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${badge.cls}`}>
            {badge.label}
          </span>
        )}
      </div>
      <p className="text-xs text-gray-500">
        {m.n_labels} labels · Brier {(m.brier_score ?? 0).toFixed(3)} · ECE {(m.ece ?? 0).toFixed(3)}
        {typeof m.margin_of_error === "number" ? ` · ±${m.margin_of_error.toFixed(3)}` : ""}
      </p>
      {fitStatus === "preview" && (
        <p className="text-[11px] text-amber-700">
          Below the {m.stable_fit_min ?? 50}-label production threshold — shown as a
          signal, not applied to live scores.
        </p>
      )}
      <p className="text-xs text-gray-600">{m.note || ""}</p>
    </div>
  );
}

function HallucinationBlock({ data }: { data: HallucinationResponse | null }) {
  if (data === null) return <Loading />;
  if (!data.available) return <Unavailable reason="provenance store empty or unavailable" />;
  if (data.overall.n === 0) {
    return (
      <p className="text-sm text-gray-500">
        No scored extractions in the last {data.window_days} days. Numbers will populate as the platform runs.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div className="bg-gray-50 rounded p-3 text-sm">
        <div className="text-xs text-gray-500 mb-1">
          Last {data.window_days} days · {data.overall.n} scored extractions
        </div>
        <div className="flex gap-6 text-gray-900">
          <span>mean risk: <strong>{(data.overall.mean_risk * 100).toFixed(1)}%</strong></span>
          <span>high-risk rate: <strong>{(data.overall.high_risk_rate * 100).toFixed(1)}%</strong></span>
        </div>
      </div>

      <HalRateMiniTable label="By extraction method" rows={data.by_extraction_method} keyField="extraction_method" />
      <HalRateMiniTable label="By model" rows={data.by_model} keyField="model_name" />
      <HalRateMiniTable label="By source (top 10)" rows={data.by_source.slice(0, 10)} keyField="source_name" />
    </div>
  );
}

function HalRateMiniTable({
  label, rows, keyField,
}: { label: string; rows: HallucinationRow[]; keyField: keyof HallucinationRow }) {
  if (rows.length === 0) return null;
  return (
    <div>
      <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-1">{label}</h4>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-gray-200">
              <th className="py-1 pr-3">Name</th>
              <th className="py-1 pr-3">n</th>
              <th className="py-1 pr-3">Mean risk</th>
              <th className="py-1 pr-3">High-risk rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-gray-100">
                <td className="py-1 pr-3 font-mono text-gray-900 text-xs">{String(row[keyField] ?? "unknown")}</td>
                <td className="py-1 pr-3 text-gray-700">{row.n}</td>
                <td className="py-1 pr-3 text-gray-700">{(row.mean_risk * 100).toFixed(1)}%</td>
                <td className="py-1 pr-3 text-gray-700">{(row.high_risk_rate * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DriftCard({
  label, data, keyField,
}: { label: string; data: DriftResponse | null; keyField: string }) {
  if (data === null) {
    return <div className="border border-gray-200 rounded-lg p-4"><Loading /></div>;
  }
  const verdictTone: Record<string, string> = {
    // Neutral grey — NOT green — so a thin/empty window never reads as a
    // confident 'stable' (the methodology page exists to show gaps honestly).
    insufficient_data: "bg-gray-100 text-gray-600 border-gray-300",
    stable: "bg-teal-50 text-teal-800 border-teal-200",
    minor: "bg-yellow-50 text-yellow-800 border-yellow-200",
    notable: "bg-orange-50 text-orange-800 border-orange-200",
    significant: "bg-red-50 text-red-800 border-red-200",
  };
  const tone = verdictTone[data.verdict] || "bg-gray-50 text-gray-800 border-gray-200";
  const verdictLabel = data.verdict.replace(/_/g, " ");

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-3">
      <header className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">{label}</h3>
        <span className={`text-xs px-2 py-0.5 rounded border ${tone}`}>{verdictLabel}</span>
      </header>
      <div className="text-xs text-gray-500">
        KL divergence:{" "}
        <strong className="text-gray-900 font-mono">{data.kl_divergence.toFixed(3)}</strong>
        {" · "}{data.recent_count} recent / {data.baseline_count} baseline
      </div>
      {data.top_shifts && data.top_shifts.length > 0 && (
        <div>
          <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-1">Top shifts</h4>
          <ul className="text-xs space-y-0.5">
            {data.top_shifts.slice(0, 5).map((s, i) => {
              const name = String(s[keyField] ?? s.display ?? "unknown");
              const delta = Number(s.delta);
              const sign = delta >= 0 ? "+" : "";
              return (
                <li key={i} className="flex items-center justify-between">
                  <code className="text-gray-700 font-mono truncate max-w-[60%]">{name}</code>
                  <span className={delta >= 0 ? "text-teal-700" : "text-red-700"}>
                    {sign}{(delta * 100).toFixed(1)}pp
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {data.notes && <p className="text-xs text-gray-500 italic">{data.notes}</p>}
    </div>
  );
}

function DocLink({
  href, label, description,
}: { href: string; label: string; description: string }) {
  return (
    <li>
      <a href={href} target="_blank" rel="noreferrer"
         className="flex items-start gap-2 text-teal-700 hover:underline">
        <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <span>
          <span className="font-medium">{label}</span>
          <span className="text-gray-600"> — {description}</span>
          <ExternalLink className="inline w-3 h-3 ml-1" />
        </span>
      </a>
    </li>
  );
}
