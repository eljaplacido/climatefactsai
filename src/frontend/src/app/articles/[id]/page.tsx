import { notFound } from "next/navigation";
import type { Metadata } from "next";
import type { ArticleDetail, ContentCategory } from "@/types";
import CredibilityGauge from "@/components/CredibilityGauge";
import ClaimCard from "@/components/ClaimCard";
import Markdown from "@/components/Markdown";
import ArticleQA from "@/components/ArticleQA";
import SimilarArticles from "@/components/SimilarArticles";
import WeatherContext from "@/components/WeatherContext";
import DecomposedConfidenceChart from "@/components/DecomposedConfidenceChart";
import ClaimCategoryBreakdown from "@/components/ClaimCategoryBreakdown";
import EvidenceTimeline from "@/components/EvidenceTimeline";
import dynamic from "next/dynamic";
import ShareButton from "@/components/ShareButton";
import BookmarkButton from "@/components/BookmarkButton";
import AskAboutButton from "@/components/AskAboutButton";
import ArticleExportButtons from "@/components/ArticleExportButtons";
import FullArticlePanel from "@/components/FullArticlePanel";
import WeatherTrendCard from "@/components/WeatherTrendCard";
import KnowledgeGraphMini from "@/components/KnowledgeGraphMini";
import TopicFeedbackButton from "@/components/TopicFeedbackButton";
import SDGChips from "@/components/SDGChips";
import ReanalyzeButton from "@/components/ReanalyzeButton";
import ArgumentationGraph from "@/components/ArgumentationGraph";
import Link from "next/link";
import { Beaker, BarChart3, Scale, Eye, TrendingUp, Info, Loader2, CheckCircle2, AlertCircle, Clock, BookOpen, Leaf, Recycle, Zap, CloudSun, Landmark, ExternalLink, AlertTriangle } from "lucide-react";
import { formatCredibilityPlain } from "@/lib/plainLanguage";
import ArticleMapBridge from "@/components/ArticleMapBridge";
import ClimateMiniMap from "@/components/ClimateMiniMap";

const ArticleDetailTabs = dynamic(() => import("@/components/ArticleDetailTabs"), {
  ssr: false,
});

async function getArticle(id: string): Promise<ArticleDetail | null> {
  const isServer = typeof window === "undefined";
  const apiBases = isServer
    ? [
        process.env.API_INTERNAL_URL,
        process.env.NEXT_PUBLIC_API_URL,
        "http://localhost:5400",
      ]
    : [process.env.NEXT_PUBLIC_API_URL, "http://localhost:5400"];

  for (const base of apiBases) {
    if (!base) continue;
    try {
      const res = await fetch(`${base}/api/v2/articles/${encodeURIComponent(id)}`, {
        next: { revalidate: 10 },
      });
      if (!res.ok) continue;
      return (await res.json()) as ArticleDetail;
    } catch {
      continue;
    }
  }

  return null;
}

const CATEGORY_ICONS: Record<string, any> = {
  scientific_causal: Beaker,
  statistical: BarChart3,
  policy: Scale,
  anecdotal: Eye,
  predictive: TrendingUp,
};

const CATEGORY_LABELS: Record<string, string> = {
  scientific_causal: "Scientific/Causal",
  statistical: "Statistical",
  policy: "Policy",
  anecdotal: "Anecdotal",
  predictive: "Predictive",
};

const CONTENT_CATEGORY_CONFIG: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  climate_science: { label: "Climate Science", icon: Beaker, color: "text-blue-700", bg: "bg-blue-50 border-blue-200" },
  sustainability: { label: "Sustainability", icon: Leaf, color: "text-green-700", bg: "bg-green-50 border-green-200" },
  circular_economy: { label: "Circular Economy", icon: Recycle, color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200" },
  green_transition: { label: "Green Transition", icon: Zap, color: "text-yellow-700", bg: "bg-yellow-50 border-yellow-200" },
  localized_forecast: { label: "Local Forecast", icon: CloudSun, color: "text-cyan-700", bg: "bg-cyan-50 border-cyan-200" },
  policy: { label: "Policy & Regulation", icon: Landmark, color: "text-purple-700", bg: "bg-purple-50 border-purple-200" },
};

function estimateReadingTime(text: string): number {
  const words = text.trim().split(/\s+/).length;
  return Math.max(1, Math.ceil(words / 200));
}

// Slice 5b (2026-05-25) — full OG + Twitter card metadata so social
// crawlers (Twitter, LinkedIn, Facebook, Slack) render rich previews
// with the article's OG image, summary, and canonical URL. Prior
// version emitted only basic title + description, no image, no Twitter
// card — links looked generic and engagement was suppressed. OG image
// at /api/og-image/{id} already exists in api/og_image_routes.py.
const API_URL_FOR_OG =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const article = await getArticle(params.id);
  if (!article) {
    return {
      title: "Article not found",
      robots: { index: false, follow: false },
    };
  }
  const title = article.title || "Climate article";
  const description =
    article.executive_brief ||
    article.excerpt ||
    "Verified climate news on Climatefacts.ai";
  const ogImage = `${API_URL_FOR_OG}/api/og-image/${params.id}`;
  const canonical = `/articles/${params.id}`;
  return {
    title: `${title} · Climatefacts.ai`,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      description,
      url: canonical,
      type: "article",
      images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
      publishedTime: article.published_date || undefined,
      siteName: "Climatefacts.ai",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
  };
}

export default async function ArticlePage({ params }: { params: { id: string } }) {
  const article = await getArticle(params.id);
  if (!article) return notFound();

  const verificationRate = article.claim_count > 0
    ? Math.round((article.verified_claim_count / article.claim_count) * 100)
    : 0;

  const reliabilityScore = article.reliability_score ?? 0;
  const credibilityLevel = article.overall_credibility ?? "UNVERIFIED";

  // Estimate reading time from available text
  const readableText = article.analysis_article_html || article.full_text || article.excerpt || "";
  const readingTime = estimateReadingTime(readableText);

  // Category config
  const categoryConfig = article.content_category
    ? CONTENT_CATEGORY_CONFIG[article.content_category]
    : null;

  return (
    <main className="max-w-4xl mx-auto" aria-labelledby="article-title">
      <div className="mb-6">
        <Link href="/search" className="text-sm text-clilens-primary hover:underline">
          &larr; Back to search
        </Link>
      </div>

      <article className="bg-white rounded-xl border border-gray-200 shadow-sm">
        {/* Header with Credibility Gauge */}
        <header className="p-6 border-b border-gray-100">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-sm text-gray-500">{article.source_name}</p>
                {/* Category badge */}
                {categoryConfig && (
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${categoryConfig.bg} ${categoryConfig.color}`}>
                    <categoryConfig.icon className="h-3 w-3" />
                    {categoryConfig.label}
                  </span>
                )}
              </div>
              <h1 id="article-title" className="mt-1 text-2xl font-bold text-gray-900">{article.title}</h1>
              <div className="mt-2 flex items-center gap-3 text-sm text-gray-500 flex-wrap">
                {article.published_date && (
                  <span>
                    {new Date(article.published_date).toLocaleDateString("en-GB", {
                      day: "numeric", month: "long", year: "numeric",
                    })}
                  </span>
                )}
                {article.author && <span>&bull; {article.author}</span>}
                <span className="inline-flex items-center gap-1">
                  <BookOpen className="h-3.5 w-3.5" />
                  {readingTime} min read
                </span>
                {article.analysis_article_generated_at && (
                  <span className="text-gray-400">
                    Analyzed {new Date(article.analysis_article_generated_at).toLocaleDateString("en-GB")}
                  </span>
                )}
                {/* chat-as-heart (2026-05-28) — article-level ask
                    button. Most prominent placement on the page so
                    users see "I can ask about this article" the
                    moment they land. Pre-fills with title + source.
                    2026-05-28 hotfix: switched from inline <button onClick>
                    to AskAboutButton component because this is a SERVER
                    component — Next.js 13+ app router disallows passing
                    onClick to native buttons in server components. The
                    AskAboutButton is "use client" so it works. Was
                    crashing the entire article page with HTTP 500. */}
                <div className="ml-auto">
                  <AskAboutButton
                    prompt={`Explain this article in plain language and tell me what to take from it. Title: "${article.title ?? "Untitled"}". Source: ${article.source_name || "unknown"}. Walk me through the key claims, their credibility, and whether I should trust this reporting.`}
                    ariaLabel="Ask the assistant about this article"
                    variant="chip"
                  />
                </div>
              </div>

              {/* Prominent original article link */}
              {article.url && (
                <div className="mt-3">
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-clilens-primary text-white rounded-lg hover:bg-clilens-teal-700 transition text-sm font-medium"
                  >
                    <ExternalLink className="h-4 w-4" />
                    View Original Article
                  </a>
                </div>
              )}
            </div>

            {/* Credibility Gauge */}
            <div className="flex-shrink-0">
              <CredibilityGauge
                score={reliabilityScore ?? 0}
                level={credibilityLevel ?? "UNKNOWN"}
                decomposedConfidence={article.decomposed_confidence}
                size="lg"
              />
            </div>
          </div>

          {/* Stats row */}
          <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-gray-600">
            <span>{article.claim_count} claims assessed</span>
            {/* Slice 4 (2026-05-25) — Limited Evidence badge fires when
                claim count is below the LIMITED_EVIDENCE_THRESHOLD in
                shared/reliability_scorer.py (currently 3). Visibly
                signals to readers that the credibility chip is based
                on thin claim coverage, even if the article passes
                source-credibility heuristics. */}
            {article.claim_count > 0 && article.claim_count < 3 && (
              <span
                className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded-full bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-700"
                title="Fewer than 3 verified claims — credibility label is provisional"
                data-testid="limited-evidence-badge"
              >
                <AlertTriangle className="h-3 w-3" />
                Limited evidence
              </span>
            )}
            {article.claim_count > 0 && (
              <>
                {/* Check if claims have error justifications (verification incomplete) */}
                {reliabilityScore === 0 && verificationRate === 100 ? (
                  <span className="inline-flex items-center gap-1.5 text-amber-600">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="font-medium">Verification incomplete — results pending</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <span className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <span
                        className="block h-2 bg-gradient-to-r from-clilens-primary to-clilens-teal-600"
                        style={{ width: `${verificationRate}%` }}
                      />
                    </span>
                    <span className="font-medium text-clilens-teal-700">{verificationRate}% verified</span>
                  </span>
                )}
              </>
            )}
            {/* Bookmark & Share */}
            <BookmarkButton articleId={article.article_id ?? ""} />
            <ShareButton
              articleId={article.article_id ?? ""}
              title={article.title ?? ""}
              excerpt={article.executive_brief || article.excerpt || ""}
            />
            {/* Export buttons (Professional+) — POST + blob download via
                axios client so the Authorization header lands; the prior
                <a href> GET was hitting routes that don't exist. */}
            <ArticleExportButtons articleId={article.article_id ?? ""} />
          </div>

          {/* Claims by category pills */}
          {article.claims_by_category && Object.keys(article.claims_by_category).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(article.claims_by_category).map(([cat, count]) => {
                const CatIcon = CATEGORY_ICONS[cat] || BarChart3;
                return (
                  <span
                    key={cat}
                    className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200"
                  >
                    <CatIcon className="h-3 w-3" />
                    <span>{CATEGORY_LABELS[cat] || cat}</span>
                    <span className="font-bold text-gray-800">{count}</span>
                  </span>
                );
              })}
            </div>
          )}

          {/* Phase 2J (2026-05-23) — plain-language interpretation of the
              article's reliability score. Turns "88/100" into a
              templated sentence so non-specialist readers get the
              meaning without needing to parse the scale. */}
          {(() => {
            const plain = formatCredibilityPlain(reliabilityScore, {
              entity: "This article",
              sampleSize: article.claim_count,
            });
            if (!plain.sentence) return null;
            const toneClass =
              plain.tone === "alert"
                ? "text-red-700"
                : plain.tone === "warn"
                  ? "text-amber-700"
                  : "text-emerald-700";
            return (
              <p
                className={`mt-3 text-xs leading-snug ${toneClass}`}
                data-testid="article-header-plain-language"
              >
                {plain.sentence}
              </p>
            );
          })()}
        </header>

        <div className="p-6 space-y-8">
          {/* Verification warning: some claims have error justifications.
              Defensive null-guard: justification can be undefined for
              claims with no fact_check OR with a fact_check that's
              still pending — calling .toLowerCase() on undefined was
              crashing the whole page render with "Cannot read
              properties of undefined (reading 'toLowerCase')". */}
          {article.claims_status === "completed" && article.claims?.some(
            (c: any) => {
              const j = c?.fact_check?.justification;
              if (typeof j !== "string") return false;
              const lower = j.toLowerCase();
              return lower.includes("error") || lower.includes("unavailable");
            }
          ) && (
            <div className="flex items-center space-x-2 px-4 py-3 rounded-lg border bg-amber-50 border-amber-200">
              <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" />
              <span className="text-sm font-medium text-amber-700">
                Some claims could not be verified — verification will be retried automatically.
              </span>
            </div>
          )}

          {/* Claims status transparency + Re-run analysis */}
          {article.claims_status && article.claims_status !== "completed" && (
            <div className={`px-4 py-4 rounded-lg border ${
              article.claims_status === "processing"
                ? "bg-blue-50 border-blue-200"
                : article.claims_status === "failed"
                ? "bg-red-50 border-red-200"
                : "bg-gray-50 border-gray-200"
            }`}>
              <div className="flex items-center space-x-2">
                {article.claims_status === "processing" ? (
                  <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
                ) : article.claims_status === "failed" ? (
                  <AlertCircle className="h-4 w-4 text-red-600" />
                ) : (
                  <Clock className="h-4 w-4 text-gray-500" />
                )}
                <span className={`text-sm font-medium ${
                  article.claims_status === "processing" ? "text-blue-700" :
                  article.claims_status === "failed" ? "text-red-700" : "text-gray-600"
                }`}>
                  {article.claims_status === "pending" && "Claims are queued for verification"}
                  {article.claims_status === "processing" && "Claims are being verified — results will appear shortly"}
                  {article.claims_status === "failed" && "Claim verification encountered an error"}
                </span>
              </div>

              {/* Failure explanation */}
              {article.claims_status === "failed" && (
                <div className="mt-3 space-y-2">
                  <div className="text-sm text-red-700 bg-red-100 rounded p-3">
                    <p className="font-medium mb-1">Why did the analysis fail?</p>
                    <p className="text-red-600">
                      {article.claims_error_message
                        ? article.claims_error_message.includes("API")
                          ? "The AI analysis service was temporarily unavailable. This can happen due to API rate limits or service outages."
                          : article.claims_error_message.includes("too short")
                          ? "The article text was too short for meaningful claim extraction. We need at least 100 characters of content."
                          : article.claims_error_message.includes("timeout")
                          ? "The analysis took too long and timed out. Complex articles with many claims may need more processing time."
                          : `Technical details: ${article.claims_error_message}`
                        : "An unexpected error occurred during claim extraction or verification."
                      }
                    </p>
                  </div>
                  <ReanalyzeButton
                    articleId={article.article_id}
                    label="Re-run Analysis"
                    className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors"
                  />
                </div>
              )}

              {/* Pending — offer manual trigger */}
              {article.claims_status === "pending" && (
                <div className="mt-3">
                  <p className="text-xs text-gray-500 mb-2">
                    The automated pipeline will process this article within 2 hours. You can also trigger analysis manually.
                  </p>
                  <ReanalyzeButton
                    articleId={article.article_id}
                    label="Analyze Now"
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                  />
                </div>
              )}
            </div>
          )}

          {/* Executive Brief — prominent display */}
          {article.executive_brief && (
            <div className="bg-gradient-to-r from-clilens-teal-50 to-blue-50 border border-clilens-teal-200 rounded-xl p-6">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-10 h-10 bg-clilens-primary rounded-full flex items-center justify-center">
                  <Info className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-900 mb-2">Executive Brief</h3>
                  <p className="text-base text-gray-700 leading-relaxed">{article.executive_brief}</p>
                </div>
              </div>
            </div>
          )}

          {/* Enriched Climate Context — localized weather/climate intelligence */}
          {(article as any).enriched_excerpt && (
            <div className="bg-gradient-to-r from-teal-50 to-cyan-50 border border-teal-200 rounded-xl p-6">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-10 h-10 bg-teal-600 rounded-full flex items-center justify-center">
                  <CloudSun className="h-5 w-5 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-bold text-gray-900 mb-2">In-Depth Analysis</h3>
                  <p className="text-base text-gray-700 leading-relaxed mb-3">{(article as any).enriched_excerpt}</p>
                  {(article as any).climate_context_summary && (
                    <div className="mt-3 p-3 bg-white/60 rounded-lg border border-teal-100">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-teal-100 text-teal-800">
                          Local Climate Context
                        </span>
                        {(article as any).enrichment_metadata?.temperature_trend && (
                          <span className="text-xs text-gray-500">
                            Trend: {(article as any).enrichment_metadata.temperature_trend}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-teal-800 leading-relaxed">{(article as any).climate_context_summary}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Stage 2 (M2) — Weather + 5-yr temperature trend card.
              Reads enrichment_metadata.weather + .temperature_trend
              (populated by ArticleEnrichmentService at enrichment time).
              Renders nothing for older articles without the metadata. */}
          {(article as any).enrichment_metadata && (
            <WeatherTrendCard
              weather={(article as any).enrichment_metadata.weather}
              trend={(article as any).enrichment_metadata.temperature_trend}
              countryCode={(article as any).country_code}
            />
          )}

          {/* Stage 2 (M1) — Knowledge graph mini-view. Fetches
              /api/carf/entity-graph/{article_id} and renders entities,
              relationships, and articles connected via shared entities.
              Powered by clilens-lane-a-entity worker on GX10. */}
          {(article as any).article_id && (
            <KnowledgeGraphMini articleId={(article as any).article_id} />
          )}

          {/* Stage 6 (M7) — UN SDG chips. Calls /api/sdg/tag against
              the brief + excerpt, links each chip to /sdg/[goal_id]
              for cross-artifact browse. */}
          {(article.executive_brief || (article as any).enriched_excerpt) && (
            <div className="px-1">
              <SDGChips
                text={[
                  article.title,
                  article.executive_brief,
                  (article as any).enriched_excerpt,
                ].filter(Boolean).join(" ")}
                maxChips={6}
              />
            </div>
          )}

          {/* Stage 3 (M4) — topic feedback. User flags slip-through
              off-topic articles; daemon excludes flagged IDs from
              future selection waves. Feeds the evolving validation
              corpus. */}
          {(article as any).article_id && (
            <div className="flex justify-end">
              <TopicFeedbackButton articleId={(article as any).article_id} />
            </div>
          )}

          {/* Insight Summary (fallback if no executive brief) */}
          {!article.executive_brief && article.insight_summary && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start space-x-2">
                <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-semibold text-blue-900 mb-1">Analysis Summary</h3>
                  <p className="text-sm text-blue-800">{article.insight_summary}</p>
                </div>
              </div>
            </div>
          )}

          {/* Polish wave 1 / Audit item 2 (2026-05-25) — collapsible
              full source article. Executive Brief + Enriched In-Depth
              above are intentionally short summaries; this surfaces
              the underlying 1500-3000-word source body when readers
              want it. Hidden by default to keep the page concise. */}
          {(article as any).extracted_text && (
            <FullArticlePanel
              extractedText={(article as any).extracted_text}
              sourceUrl={(article as any).url || (article as any).source_url}
            />
          )}

          {/* Reliability Breakdown */}
          {article.reliability_breakdown && Object.keys(article.reliability_breakdown).length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-gray-900">Reliability Breakdown</h2>
                <Link
                  href={`/articles/${article.article_id ?? params.id}/transparency`}
                  className="text-xs text-clilens-primary hover:underline"
                >
                  View full methodology &rarr;
                </Link>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(article.reliability_breakdown).map(([key, factor]) => {
                  const f = factor as { label: string; score: number; weight: number; weighted_score: number };
                  const score = f.score != null && !isNaN(f.score) ? Math.round(f.score * 100) : 0;
                  const weight = f.weight != null && !isNaN(f.weight) ? Math.round(f.weight * 100) : 0;
                  const barColor = score >= 75 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : score > 0 ? 'bg-red-500' : 'bg-gray-300';
                  return (
                    <div key={key} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-600">{f.label || key.replace(/_/g, ' ')}</span>
                        <span className="text-xs font-semibold text-gray-900">
                          {score}%
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${barColor} transition-all`}
                          style={{ width: `${Math.max(score, score > 0 ? 4 : 0)}%` }}
                        />
                      </div>
                      <div className="mt-1 flex items-center justify-between">
                        <p className="text-[10px] text-gray-400">
                          Weight: {weight}%
                        </p>
                        <Link
                          href={`/articles/${article.article_id ?? params.id}/transparency#${key}`}
                          className="text-[10px] text-clilens-primary hover:underline"
                        >
                          How computed?
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Tabbed content: Analysis | Raw Claims | Evidence */}
          <ArticleDetailTabs
            analysisHtml={article.analysis_article_html}
            excerpt={article.excerpt}
            fullText={article.full_text}
            claims={article.claims ?? []}
          />

          {/* Infographic — embedded SVGs */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Visual Summary</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {(["summary", "claims", "confidence", "reliability"] as const).map((tpl) => (
                <div
                  key={tpl}
                  className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden"
                >
                  <img
                    src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400"}/api/articles/${article.article_id ?? params.id}/infographic?template=${tpl}`}
                    alt={`${tpl} infographic for ${article.title ?? ""}`}
                    className="w-full h-auto"
                    loading="lazy"
                  />
                  <div className="px-3 py-2 text-center">
                    <span className="text-xs font-medium text-gray-600 capitalize">{tpl} Card</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Phase 4A (2026-05-23) — Article → Map bridge per the
              original strategic memo §3.6 ("highest-impact UX move").
              Turns the article from dead-end into a launchpad for
              map / passport / deep-search. Renders only when the
              article has a country code OR at least one tag. */}

          {article.country_code && (
            <div className="mt-8 mb-6">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">
                Country Context
              </h3>
              <ClimateMiniMap
                countries={[article.country_code]}
                title={article.country_code}
                layer="climate_risk"
              />
            </div>
          )}

          <ArticleMapBridge
            articleId={article.article_id ?? ""}
            articleTitle={article.title ?? ""}
            countryCode={article.country_code}
            tags={article.tags ?? []}
          />

          {/* Local Weather Context */}
          <WeatherContext articleId={article.article_id ?? ""} />

          {/* Knowledge Graph / Argumentation */}
          <ArgumentationGraph articleId={article.article_id ?? ""} />

          {/* Similar Articles */}
          <SimilarArticles articleId={article.article_id ?? ""} />

          {/* Article Q&A */}
          <ArticleQA
            articleId={article.article_id ?? ""}
            articleTitle={article.title ?? ""}
            contentCategory={article.content_category}
            claims={article.claims ?? []}
          />

          {/* Advanced Insights — Transparency Report */}
          <section className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Advanced Insights</h2>
            <p className="text-sm text-gray-600 mb-4">
              Detailed transparency breakdown, evidence chains with traceable sources, causal analysis, and confidence intervals.
            </p>
            <Link
              href={`/articles/${article.article_id ?? params.id}/transparency`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition text-sm"
            >
              View Transparency Report
            </Link>
          </section>

          {/* AI Analysis disclaimer */}
          <div className="pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-400">
              This analysis was generated by AI. Always refer to the{" "}
              {article.url ? (
                <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-clilens-primary hover:underline">
                  original article
                </a>
              ) : "original article"}{" "}
              for the authoritative source.
            </p>
          </div>
        </div>
      </article>
    </main>
  );
}
