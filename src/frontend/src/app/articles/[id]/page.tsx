import { notFound } from "next/navigation";
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
import ArticleDetailTabs from "@/components/ArticleDetailTabs";
import ShareButton from "@/components/ShareButton";
import BookmarkButton from "@/components/BookmarkButton";
import ReanalyzeButton from "@/components/ReanalyzeButton";
import Link from "next/link";
import { Beaker, BarChart3, Scale, Eye, TrendingUp, Info, Loader2, CheckCircle2, AlertCircle, Clock, BookOpen, Leaf, Recycle, Zap, CloudSun, Landmark, ExternalLink, AlertTriangle } from "lucide-react";

async function getArticle(id: string): Promise<ArticleDetail | null> {
  const isServer = typeof window === 'undefined';
  const base = isServer
    ? (process.env.API_INTERNAL_URL || "http://api:8000")
    : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400");

  try {
    const res = await fetch(`${base}/api/v2/articles/${encodeURIComponent(id)}`, {
      next: { revalidate: 10 },
    });
    if (!res.ok) return null;
    return (await res.json()) as ArticleDetail;
  } catch {
    return null;
  }
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

export async function generateMetadata({ params }: { params: { id: string } }) {
  const article = await getArticle(params.id);
  if (!article) return { title: "Article Not Found" };
  return {
    title: `${article.title} — CliLens.AI Analysis`,
    description: article.executive_brief || article.excerpt || article.title,
    openGraph: {
      title: article.title,
      description: article.executive_brief || article.excerpt || "",
      type: "article",
      siteName: "CliLens.AI",
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
    <div className="max-w-4xl mx-auto">
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
              <h1 className="mt-1 text-2xl font-bold text-gray-900">{article.title}</h1>
              <div className="mt-2 flex items-center gap-3 text-sm text-gray-500">
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
                score={reliabilityScore}
                level={credibilityLevel}
                decomposedConfidence={article.decomposed_confidence}
                size="lg"
              />
            </div>
          </div>

          {/* Stats row */}
          <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-gray-600">
            <span>{article.claim_count} claims assessed</span>
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
            <BookmarkButton articleId={article.article_id} />
            <ShareButton
              articleId={article.article_id}
              title={article.title}
              excerpt={article.executive_brief || article.excerpt}
            />
            {/* Export buttons (Standard+ tier) */}
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400"}/api/export/article/${article.article_id}?format=csv`}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-clilens-primary border border-gray-200 rounded hover:border-clilens-primary transition"
              target="_blank"
              rel="noopener noreferrer"
            >
              CSV
            </a>
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400"}/api/export/article/${article.article_id}?format=pdf`}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-clilens-primary border border-gray-200 rounded hover:border-clilens-primary transition"
              target="_blank"
              rel="noopener noreferrer"
            >
              PDF
            </a>
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
        </header>

        <div className="p-6 space-y-8">
          {/* Verification warning: some claims have error justifications */}
          {article.claims_status === "completed" && article.claims?.some(
            (c: any) => c.fact_check?.justification &&
              (c.fact_check.justification.toLowerCase().includes("error") ||
               c.fact_check.justification.toLowerCase().includes("unavailable"))
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

          {/* Reliability Breakdown */}
          {article.reliability_breakdown && Object.keys(article.reliability_breakdown).length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Reliability Breakdown</h2>
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
                      <p className="mt-1 text-[10px] text-gray-400">
                        Weight: {weight}%
                      </p>
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
            claims={article.claims}
          />

          {/* Infographic — embedded SVGs */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Visual Summary</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {(["summary", "claims", "confidence"] as const).map((tpl) => (
                <div
                  key={tpl}
                  className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden"
                >
                  <img
                    src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400"}/api/articles/${article.article_id}/infographic?template=${tpl}`}
                    alt={`${tpl} infographic`}
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

          {/* Local Weather Context */}
          <WeatherContext articleId={article.article_id} />

          {/* Similar Articles */}
          <SimilarArticles articleId={article.article_id} />

          {/* Article Q&A */}
          <ArticleQA
            articleId={article.article_id}
            articleTitle={article.title}
            contentCategory={article.content_category}
            claims={article.claims}
          />

          {/* Advanced Insights — Transparency Report */}
          <section className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Advanced Insights</h2>
            <p className="text-sm text-gray-600 mb-4">
              Detailed transparency breakdown, evidence chains with traceable sources, causal analysis, and confidence intervals.
            </p>
            <Link
              href={`/articles/${article.article_id}/transparency`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition text-sm"
            >
              View Transparency Report
            </Link>
          </section>

          {/* AI Analysis disclaimer */}
          <div className="pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-400">
              This analysis was generated by AI. Always refer to the{" "}
              <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-clilens-primary hover:underline">
                original article
              </a>{" "}
              for the authoritative source.
            </p>
          </div>
        </div>
      </article>
    </div>
  );
}
