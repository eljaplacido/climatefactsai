"use client";

import { Fingerprint, ExternalLink } from "lucide-react";

/**
 * AI provenance surface — EU AI Act Article 50 + COP30 Information Integrity
 * disclosure pattern.
 *
 * Every AI-produced surface on the platform (deep-search synthesis, URL
 * analysis verdicts, chat answers, article Q&A) MUST render:
 *
 *   1. A visible `<AIProvenanceBadge>` so a sighted user immediately knows
 *      the content was AI-generated, by which model, at which prompt version.
 *      Carries `data-ai-generated="true"` for assistive tech + scrapers.
 *
 *   2. A machine-readable `<AIProvenanceJsonLd>` `<script type="application/ld+json">`
 *      payload following schema.org `CreativeWork` with `creator` set to a
 *      `SoftwareApplication` of `applicationCategory: "AIApplication"`. This
 *      is what crawlers, regulators, fact-checkers, and downstream platforms
 *      will read to verify the AI-generated disclosure.
 *
 * Together they satisfy the Article 50 "transparency obligation for AI
 * generated or manipulated text published with the purpose to inform the
 * public on matters of public interest" requirement (effective 2 Aug 2026).
 *
 * Shipped 2026-05-23 as Phase 0 day 3.
 */

export interface AIProvenancePayload {
  /** LLM model identifier — e.g. "claude-sonnet-4-6", "deepseek-chat" */
  model: string;
  /** Versioned prompt name from the registry — e.g. "deep_search_synthesis" */
  prompt_name?: string;
  /** Prompt version string — e.g. "1.0" */
  prompt_version?: string;
  /** SHA-256 fingerprint of the exact prompt body (for reproducibility) */
  prompt_fingerprint?: string;
  /** Retrieval strategy used — e.g. "internal_corpus(fts+semantic) + perplexity_external" */
  retrieval_strategy?: string;
  /** ISO 8601 timestamp the content was generated */
  timestamp: string;
  /** Top-level methodology version stamped on the page footer */
  methodology_version?: string;
  /** Surface that produced this content — used in the JSON-LD `additionalType` */
  surface?: "deep_search" | "deep_search_compare" | "url_analysis" | "article_qa" | "chat" | "research_analysis";
  /** Optional URL of the surface — used as JSON-LD `url` field */
  surface_url?: string;
  /** Optional short summary of the user-visible content for `description` */
  content_summary?: string;
}

/**
 * Build a schema.org `CreativeWork` JSON-LD payload disclosing that this
 * content was produced by an AI system. This shape is what we recommend
 * other climate platforms adopt as a community convention (CFRS spec —
 * see strategic memo §C1).
 *
 * Why CreativeWork (not ClaimReview): the synthesis is generated content,
 * not a fact-check verdict about an external claim. ClaimReview is reserved
 * for our per-article credibility report. Using the wrong type confuses
 * Google Rich Results and downstream fact-check aggregators.
 */
export function buildAiJsonLd(provenance: AIProvenancePayload): Record<string, any> {
  const shortModel = provenance.model?.replace(/-\d{4}-\d{2}-\d{2}$/, "") ?? "unknown-model";
  const promptDisplay = provenance.prompt_name
    ? `${provenance.prompt_name}${provenance.prompt_version ? `@${provenance.prompt_version}` : ""}`
    : undefined;

  const surfaceCategory: Record<string, string> = {
    deep_search: "ResearchAnalysis",
    deep_search_compare: "ComparativeAnalysis",
    url_analysis: "FactCheckAnalysis",
    article_qa: "QuestionAnswerInteraction",
    chat: "ChatInteraction",
    research_analysis: "ScholarlyAnalysis",
  };

  const payload: Record<string, any> = {
    "@context": "https://schema.org",
    "@type": "CreativeWork",
    name: "AI-generated climate analysis",
    description: provenance.content_summary || undefined,
    inLanguage: "en",
    datePublished: provenance.timestamp,
    isAccessibleForFree: true,
    // AI authorship — the core EU AI Act disclosure
    creator: {
      "@type": "SoftwareApplication",
      name: shortModel,
      applicationCategory: "AIApplication",
      additionalType: surfaceCategory[provenance.surface || "deep_search"] || "ResearchAnalysis",
      softwareVersion: promptDisplay || provenance.prompt_version || undefined,
      // SHA-256 fingerprint is the verifiable handle for reproducibility
      identifier: provenance.prompt_fingerprint
        ? { "@type": "PropertyValue", propertyID: "prompt_sha256", value: provenance.prompt_fingerprint }
        : undefined,
    },
    publisher: {
      "@type": "Organization",
      name: "Climatefacts.ai",
      url: "https://climatefacts.ai",
    },
    // Non-standard extension namespace for platform-specific fields
    // (retrieval strategy, methodology version). Documented at /methodology.
    "https://climatefacts.ai/schema/v1#retrieval_strategy": provenance.retrieval_strategy || undefined,
    "https://climatefacts.ai/schema/v1#methodology_version": provenance.methodology_version || undefined,
    "https://climatefacts.ai/schema/v1#surface": provenance.surface || undefined,
    url: provenance.surface_url || undefined,
  };

  // Drop undefined keys so the rendered JSON is clean.
  const clean: Record<string, any> = {};
  for (const [k, v] of Object.entries(payload)) {
    if (v !== undefined && v !== null && v !== "") {
      clean[k] = v;
    }
  }
  // Same cleanup for nested creator object — undefined identifier/softwareVersion
  if (clean.creator && typeof clean.creator === "object") {
    const cc: Record<string, any> = {};
    for (const [k, v] of Object.entries(clean.creator)) {
      if (v !== undefined && v !== null && v !== "") cc[k] = v;
    }
    clean.creator = cc;
  }
  return clean;
}

interface AIProvenanceJsonLdProps {
  provenance: AIProvenancePayload;
}

/**
 * Emit the JSON-LD `<script>` tag. Renders nothing visually — the badge
 * component handles the user-facing surface. This MUST sit alongside the
 * badge on every AI-produced page; rendering only the badge without the
 * JSON-LD payload fails the AI-Act machine-readable disclosure clause.
 *
 * Safe to render multiple times per page — search engines deduplicate.
 */
export function AIProvenanceJsonLd({ provenance }: AIProvenanceJsonLdProps) {
  const jsonLd = buildAiJsonLd(provenance);
  return (
    <script
      type="application/ld+json"
      data-testid="ai-provenance-jsonld"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

interface AIProvenanceBadgeProps {
  provenance: AIProvenancePayload;
  variant?: "inline" | "block";
  /** When true, also renders the JSON-LD script tag. Default true. Disable
   *  only when a parent surface already emits its own JSON-LD to avoid
   *  duplicate identical payloads. */
  emitJsonLd?: boolean;
}

export default function AIProvenanceBadge({
  provenance,
  variant = "inline",
  emitJsonLd = true,
}: AIProvenanceBadgeProps) {
  const { model, prompt_name, prompt_version, timestamp, methodology_version } = provenance;

  const shortModel = model?.replace(/-\d{4}-\d{2}-\d{2}$/, "") ?? "AI";
  const displayVersion = methodology_version || prompt_version || "";

  return (
    <>
      {emitJsonLd && <AIProvenanceJsonLd provenance={provenance} />}
      <div
        data-ai-generated="true"
        data-testid="ai-provenance-badge"
        className={
          variant === "block"
            ? "bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800 rounded-lg p-3 text-xs space-y-1"
            : "inline-flex items-center gap-1.5 text-xs bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-full px-2.5 py-0.5"
        }
        aria-label={`AI-generated content using ${shortModel}${displayVersion ? ` version ${displayVersion}` : ""}`}
        role="note"
      >
        <Fingerprint className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
        <span>
          AI-produced &middot; {shortModel}
          {displayVersion && <span className="opacity-75"> &middot; v{displayVersion}</span>}
        </span>
        {variant === "block" && (
          <>
            {prompt_name && (
              <div className="text-teal-700 dark:text-teal-300">
                Prompt: <code className="font-mono">{prompt_name}</code>
                {prompt_version && ` v${prompt_version}`}
              </div>
            )}
            {provenance.retrieval_strategy && (
              <div className="text-teal-700 dark:text-teal-300">
                Retrieval: {provenance.retrieval_strategy}
              </div>
            )}
            <div className="text-teal-700 dark:text-teal-300">
              Generated: {new Date(timestamp).toLocaleString()}
            </div>
            <a
              href="/methodology"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-teal-700 dark:text-teal-300 hover:underline mt-1"
            >
              <ExternalLink className="w-3 h-3" aria-hidden="true" />
              Reproduce via methodology
            </a>
          </>
        )}
      </div>
    </>
  );
}
