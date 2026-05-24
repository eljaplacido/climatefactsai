"use client";

import Link from "next/link";
import {
  Map as MapIcon,
  Globe,
  ArrowRight,
  Search,
  GitCompare,
} from "lucide-react";

/**
 * ArticleMapBridge — Phase 4A (2026-05-23).
 *
 * The "highest-impact UX move you can ship in the next two weeks"
 * named in the very first strategic memo (§3.6, 2026-05-18). Turns the
 * article detail page from a dead-end into a launchpad for the
 * platform's other top-tier surfaces (map, deep search, country
 * passport). Pure-presentational — no fetches.
 *
 * Renders three categorised CTAs:
 *   1. Open this story's country on the map (per-country deeplink)
 *   2. Full country passport (Phase 2B surface)
 *   3. Find global insights related to this story's claims
 *      (deep-search deeplink seeded with the article title)
 *
 * Topic chips (from article tags) get their own row when present so
 * the reader can drill into one specific theme rather than the whole
 * country panel.
 *
 * Competitive bar:
 *   - Carbon Brief: links to source PDFs but not to a map. We exceed.
 *   - OWID: no per-article country deeplinks. N/A.
 *   - Climate Watch: country-keyed but no article-anchored bridge.
 *     We're the only platform that does this.
 *
 * Design rule: this section is rendered for EVERY article that has a
 * `country_code` OR at least one tag. Articles with neither don't get
 * the section (no value to show).
 */

interface ArticleMapBridgeProps {
  articleId: string;
  articleTitle: string;
  countryCode?: string | null;
  /** Display name for the country — falls back to the code if absent. */
  countryName?: string | null;
  /** Optional tags from the article — first 5 surface as topic chips. */
  tags?: string[];
}

export default function ArticleMapBridge({
  articleId,
  articleTitle,
  countryCode,
  countryName,
  tags = [],
}: ArticleMapBridgeProps) {
  const hasCountry = Boolean(countryCode && countryCode.length === 2);
  const hasTags = tags.length > 0;
  if (!hasCountry && !hasTags) return null;

  const cc = (countryCode || "").toUpperCase();
  const displayCountry = countryName || cc;
  // Seed deep-search with the article title so the reader lands on a
  // pre-filled query for global insights related to THIS story.
  const deepSearchQuery = encodeURIComponent(
    articleTitle.length > 120 ? articleTitle.slice(0, 120) : articleTitle,
  );

  return (
    <section
      className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-5"
      aria-labelledby="article-map-bridge-title"
      data-testid="article-map-bridge"
    >
      <div className="flex items-center gap-2 mb-2">
        <Globe className="w-4 h-4 text-teal-600 dark:text-teal-400" aria-hidden="true" />
        <h2
          id="article-map-bridge-title"
          className="text-base font-semibold text-gray-900 dark:text-slate-100"
        >
          This story on the world
        </h2>
      </div>
      <p className="text-xs text-gray-600 dark:text-slate-400 mb-4">
        See how the claims and themes in this article connect to the broader
        data — open the country on the map, dive into its full climate
        passport, or run a deep search across our corpus.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {hasCountry && (
          <Link
            href={`/map?country=${cc}&fromArticle=${encodeURIComponent(articleId)}`}
            className="group flex flex-col items-start gap-1.5 p-3 rounded-md border border-gray-200 dark:border-slate-700 hover:border-teal-400 dark:hover:border-teal-500 hover:bg-teal-50 dark:hover:bg-teal-900/20 transition-colors"
            data-testid="article-map-bridge-map-link"
          >
            <div className="flex items-center gap-1.5 text-teal-700 dark:text-teal-300">
              <MapIcon className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="text-xs font-semibold uppercase tracking-wider">
                Map view
              </span>
            </div>
            <p className="text-sm font-medium text-gray-900 dark:text-slate-100 group-hover:text-teal-900 dark:group-hover:text-teal-100">
              Open {displayCountry} on the map
            </p>
            <p className="text-[11px] text-gray-500 dark:text-slate-400">
              Article density · temperature anomaly · climate risk
            </p>
          </Link>
        )}
        {hasCountry && (
          <Link
            href={`/country/${cc}?fromArticle=${encodeURIComponent(articleId)}`}
            className="group flex flex-col items-start gap-1.5 p-3 rounded-md border border-gray-200 dark:border-slate-700 hover:border-teal-400 dark:hover:border-teal-500 hover:bg-teal-50 dark:hover:bg-teal-900/20 transition-colors"
            data-testid="article-map-bridge-passport-link"
          >
            <div className="flex items-center gap-1.5 text-teal-700 dark:text-teal-300">
              <GitCompare className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="text-xs font-semibold uppercase tracking-wider">
                Country passport
              </span>
            </div>
            <p className="text-sm font-medium text-gray-900 dark:text-slate-100 group-hover:text-teal-900 dark:group-hover:text-teal-100">
              {displayCountry} climate passport
            </p>
            <p className="text-[11px] text-gray-500 dark:text-slate-400">
              KPIs · climate data · sources · claim ledger
            </p>
          </Link>
        )}
        <Link
          href={`/deep-search?q=${deepSearchQuery}${hasCountry ? `&country=${cc}` : ""}&fromArticle=${encodeURIComponent(articleId)}`}
          className="group flex flex-col items-start gap-1.5 p-3 rounded-md border border-gray-200 dark:border-slate-700 hover:border-teal-400 dark:hover:border-teal-500 hover:bg-teal-50 dark:hover:bg-teal-900/20 transition-colors"
          data-testid="article-map-bridge-deep-search-link"
        >
          <div className="flex items-center gap-1.5 text-teal-700 dark:text-teal-300">
            <Search className="w-3.5 h-3.5" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-wider">
              Global insights
            </span>
          </div>
          <p className="text-sm font-medium text-gray-900 dark:text-slate-100 group-hover:text-teal-900 dark:group-hover:text-teal-100">
            Search the corpus for related claims
          </p>
          <p className="text-[11px] text-gray-500 dark:text-slate-400">
            Pre-seeded with this article's title
          </p>
        </Link>
      </div>

      {hasTags && (
        <div
          className="mt-4 pt-4 border-t border-gray-100 dark:border-slate-800"
          data-testid="article-map-bridge-topics"
        >
          <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-slate-400 mb-2">
            Or follow a specific theme
          </p>
          <div className="flex flex-wrap gap-1.5">
            {tags.slice(0, 5).map((tag) => (
              <Link
                key={tag}
                href={`/search?q=${encodeURIComponent(tag)}${hasCountry ? `&country=${cc}` : ""}`}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-200 hover:bg-teal-100 dark:hover:bg-teal-900/40 hover:text-teal-800 dark:hover:text-teal-200 rounded-full transition-colors"
                data-testid="article-map-bridge-topic-chip"
              >
                {tag}
                <ArrowRight className="w-3 h-3 opacity-50" aria-hidden="true" />
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
