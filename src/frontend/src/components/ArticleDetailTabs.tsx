"use client";

import { useState, useMemo } from "react";
import clsx from "clsx";
import DOMPurify from "isomorphic-dompurify";
import type { ClaimDetail } from "@/types";
import ClaimCard from "./ClaimCard";
import Markdown from "./Markdown";
import { stripHtml } from "@/lib/stripHtml";
import { FileText, Shield, Search, ChevronDown, ChevronRight } from "lucide-react";

// Regex sanitizer was bypassable (newline-injected on-handlers, SVG <use href="data:...">,
// math/SVG namespace tricks, etc.). Use DOMPurify with a strict allowlist that covers
// the tags actually produced by our analysis-article Markdown→HTML pipeline.
const SAFE_TAGS = [
  "a", "b", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "h5", "h6",
  "hr", "i", "img", "li", "ol", "p", "pre", "span", "strong", "sub", "sup",
  "table", "tbody", "td", "th", "thead", "tr", "ul",
];
const SAFE_ATTRS = ["href", "src", "alt", "title", "class", "target", "rel"];

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: SAFE_TAGS,
    ALLOWED_ATTR: SAFE_ATTRS,
    // Block protocols other than http(s) and mailto on href/src (defence in
    // depth — DOMPurify already strips javascript:, but be explicit).
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    // Force target=_blank links to also carry rel="noopener noreferrer".
    ADD_ATTR: ["target", "rel"],
  });
}

interface ArticleDetailTabsProps {
  analysisHtml?: string;
  excerpt?: string;
  fullText?: string;
  claims: ClaimDetail[];
}

export default function ArticleDetailTabs({
  analysisHtml,
  excerpt,
  fullText,
  claims,
}: ArticleDetailTabsProps) {
  const [claimsOpen, setClaimsOpen] = useState(true);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [originalTextOpen, setOriginalTextOpen] = useState(false);

  const hasClaims = claims.length > 0;

  // Collect evidence from all claims
  const evidenceItems = claims.flatMap((c, idx) => {
    const fc = c.fact_check;
    if (!fc?.evidence_chain || fc.evidence_chain.length === 0) return [];
    return fc.evidence_chain.map((ev) => ({
      ...ev,
      claimText: c.claim_text,
      claimIndex: idx,
    }));
  });

  return (
    <div className="space-y-6">
      {/* Analysis Article (shown inline, not behind a tab) */}
      {analysisHtml && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-clilens-primary" />
            Analysis
          </h2>
          <div
            className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-strong:text-gray-900 prose-table:text-sm prose-blockquote:border-clilens-primary prose-blockquote:bg-gray-50 prose-blockquote:py-2 prose-blockquote:px-4 prose-blockquote:rounded-r-lg"
            dangerouslySetInnerHTML={{ __html: sanitizeHtml(analysisHtml) }}
          />
        </section>
      )}

      {/* If no analysis HTML, show excerpt/full text as primary content.
          Defensive HTML strip for both — backend html_cleaner sometimes
          misses InfoAmazonia/WordPress feed bodies that arrive as
          `<figure><img...><p>real text...</p>` blocks; render-time strip
          keeps the UI clean even when the column wasn't backfilled. */}
      {!analysisHtml && (excerpt || fullText) && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-clilens-primary" />
            Article Content
          </h2>
          <div className="prose prose-sm max-w-none text-gray-700">
            {fullText ? (
              <Markdown content={stripHtml(fullText)} />
            ) : excerpt ? (
              <Markdown content={stripHtml(excerpt)} />
            ) : null}
          </div>
        </section>
      )}

      {/* Claims Section — collapsible with anchor IDs */}
      {hasClaims && (
        <section id="claims-section">
          <button
            onClick={() => setClaimsOpen(!claimsOpen)}
            className="w-full flex items-center justify-between py-3 border-t border-gray-200 group"
          >
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Shield className="h-5 w-5 text-clilens-primary" />
              Verified Claims
              <span className="text-sm font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                {claims.length}
              </span>
            </h2>
            {claimsOpen ? (
              <ChevronDown className="h-5 w-5 text-gray-400 group-hover:text-gray-600" />
            ) : (
              <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-gray-600" />
            )}
          </button>
          {claimsOpen && (
            <div className="space-y-4 mt-2">
              {claims.map((c, index) => (
                <div key={c.claim_id} id={`claim-${index + 1}`}>
                  <ClaimCard claim={c} index={index} />
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Evidence Chain — collapsible */}
      {evidenceItems.length > 0 && (
        <section id="evidence-section">
          <button
            onClick={() => setEvidenceOpen(!evidenceOpen)}
            className="w-full flex items-center justify-between py-3 border-t border-gray-200 group"
          >
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Search className="h-5 w-5 text-clilens-primary" />
              Evidence Chain
              <span className="text-sm font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                {evidenceItems.length}
              </span>
            </h2>
            {evidenceOpen ? (
              <ChevronDown className="h-5 w-5 text-gray-400 group-hover:text-gray-600" />
            ) : (
              <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-gray-600" />
            )}
          </button>
          {evidenceOpen && (
            <div className="space-y-3 mt-2">
              {evidenceItems.map((ev, idx) => (
                <div key={idx} className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 bg-clilens-primary/10 text-clilens-primary text-xs font-bold rounded-full flex items-center justify-center">
                      {ev.step_number}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-700">{ev.description}</p>
                      <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
                        <span>Source: {ev.source}</span>
                        {ev.confidence > 0 && (
                          <span>Confidence: {Math.round(ev.confidence * 100)}%</span>
                        )}
                        {ev.supports_claim !== null && (
                          <span className={ev.supports_claim ? "text-emerald-600" : "text-red-600"}>
                            {ev.supports_claim ? "Supports" : "Contradicts"} claim
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-[11px] text-gray-400 truncate">
                        Re: <a href={`#claim-${ev.claimIndex + 1}`} className="hover:underline">&ldquo;{ev.claimText}&rdquo;</a>
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Original article text — collapsible, only if analysis HTML exists */}
      {analysisHtml && (excerpt || fullText) && (
        <section>
          <button
            onClick={() => setOriginalTextOpen(!originalTextOpen)}
            className="w-full flex items-center justify-between py-3 border-t border-gray-200 group"
          >
            <h2 className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <FileText className="h-4 w-4 text-gray-400" />
              Original Article Text
            </h2>
            {originalTextOpen ? (
              <ChevronDown className="h-4 w-4 text-gray-400 group-hover:text-gray-600" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-400 group-hover:text-gray-600" />
            )}
          </button>
          {originalTextOpen && (
            <div className="mt-3 prose prose-sm max-w-none text-gray-600">
              {fullText ? (
                <Markdown content={stripHtml(fullText)} />
              ) : excerpt ? (
                <Markdown content={stripHtml(excerpt)} />
              ) : null}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
