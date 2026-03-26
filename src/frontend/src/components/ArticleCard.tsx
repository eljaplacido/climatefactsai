"use client";

import Link from "next/link";
import { Calendar, User, Beaker, BarChart3, Scale, Eye, TrendingUp, Loader2, CheckCircle2, AlertCircle, Clock, Thermometer } from "lucide-react";
import { format } from "date-fns";
import { enGB } from "date-fns/locale";
import clsx from "clsx";
import type { Article } from "../types";
import CredibilityGauge from "./CredibilityGauge";
import BookmarkButton from "./BookmarkButton";
import Markdown from "./Markdown";

interface ArticleCardProps {
  article: Article;
}

const TAG_LABELS: Record<string, string> = {
  saa_ilmiot: "Weather events",
  ilmastonmuutos: "Climate change",
  kiertotalous: "Circular economy",
  vihrea_siirtyma: "Green transition",
  kestava_kehitys: "Sustainable development",
  esg: "ESG",
};

const formatTagLabel = (tag: string) => {
  const lower = tag.toLowerCase();
  if (TAG_LABELS[lower]) {
    return TAG_LABELS[lower];
  }
  return lower
    .split("_")
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
};

const CATEGORY_ICON_MAP: Record<string, any> = {
  scientific_causal: Beaker,
  statistical: BarChart3,
  policy: Scale,
  anecdotal: Eye,
  predictive: TrendingUp,
};

const CLAIMS_STATUS_CONFIG: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  pending: { label: "Claims pending", icon: Clock, color: "text-gray-500", bg: "bg-gray-50 border-gray-200" },
  processing: { label: "Verifying claims…", icon: Loader2, color: "text-blue-600", bg: "bg-blue-50 border-blue-200" },
  completed: { label: "Verification complete", icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50 border-emerald-200" },
  failed: { label: "Verification failed", icon: AlertCircle, color: "text-red-600", bg: "bg-red-50 border-red-200" },
};

const CONTENT_CAT_COLORS: Record<string, string> = {
  climate_science: "bg-blue-500",
  sustainability: "bg-green-500",
  circular_economy: "bg-emerald-500",
  green_transition: "bg-yellow-500",
  localized_forecast: "bg-cyan-500",
  policy: "bg-purple-500",
};

function estimateReadingTime(text?: string): number {
  if (!text) return 0;
  return Math.max(1, Math.ceil(text.trim().split(/\s+/).length / 200));
}

function ArticleCard({ article }: ArticleCardProps) {
  const verificationRate = article.claim_count > 0
    ? Math.round((article.verified_claim_count / article.claim_count) * 100)
    : 0;

  const reliabilityScore = article.reliability_score ?? article.source_credibility_score ?? 0;
  const readingTime = estimateReadingTime(article.excerpt);
  const categoryColor = article.content_category
    ? CONTENT_CAT_COLORS[article.content_category] || "bg-gray-400"
    : null;

  return (
    <Link
      href={`/articles/${article.article_id}`}
      className={clsx(
        "block bg-white rounded-xl shadow-sm overflow-hidden group",
        "border-l-4 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300",
        article.overall_credibility === "HIGH" ? "border-l-emerald-400 border-r border-t border-b border-r-gray-200 border-t-gray-200 border-b-gray-200" :
        article.overall_credibility === "LOW" ? "border-l-red-400 border-r border-t border-b border-r-gray-200 border-t-gray-200 border-b-gray-200" :
        "border-l-amber-400 border-r border-t border-b border-r-gray-200 border-t-gray-200 border-b-gray-200"
      )}
    >
      {/* Category color strip */}
      {categoryColor && (
        <div className={clsx("h-1 w-full", categoryColor)} />
      )}

      <div className="p-6">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900">{article.source_name}</span>
            {article.content_category && (
              <span className="text-[10px] text-gray-400 px-1.5 py-0.5 bg-gray-50 rounded border border-gray-100">
                {article.content_category.replace(/_/g, " ")}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <BookmarkButton articleId={article.article_id} size="sm" />
            <CredibilityGauge
              score={reliabilityScore}
              level={article.overall_credibility}
              size="sm"
            />
          </div>
        </div>

        <h3 className="text-xl font-bold text-gray-900 mb-3 group-hover:text-clilens-primary transition-colors line-clamp-2">
          {article.title}
        </h3>

        {/* Enriched excerpt (full paragraph) or fallback to basic excerpt */}
        {(article.enriched_excerpt || article.excerpt) && (
          <div className="text-gray-600 text-sm mb-4 line-clamp-6">
            <Markdown content={article.enriched_excerpt || article.excerpt || ""} />
          </div>
        )}

        {/* Climate context indicator */}
        {article.climate_context_summary && (
          <div className="flex items-start gap-2 mb-4 px-3 py-2 bg-teal-50 border border-teal-200 rounded-lg">
            <Thermometer className="h-4 w-4 text-teal-600 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-teal-700 line-clamp-2">{article.climate_context_summary}</p>
          </div>
        )}

        {article.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {article.tags.slice(0, 4).map((tag) => (
              <span key={tag} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full border border-gray-200">
                {formatTagLabel(tag)}
              </span>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 mb-4">
          {article.published_date && (
            <div className="flex items-center space-x-1">
              <Calendar className="h-4 w-4" />
              <span>{format(new Date(article.published_date), "dd MMM yyyy", { locale: enGB })}</span>
            </div>
          )}

          {article.author && (
            <div className="flex items-center space-x-1">
              <User className="h-4 w-4" />
              <span>{article.author}</span>
            </div>
          )}

          {readingTime > 0 && (
            <div className="flex items-center space-x-1 text-gray-400">
              <span>{readingTime} min read</span>
            </div>
          )}
        </div>

        {/* Claims-by-category pills */}
        {article.claims_by_category && Object.keys(article.claims_by_category).length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {Object.entries(article.claims_by_category).map(([cat, count]) => {
              const CatIcon = CATEGORY_ICON_MAP[cat] || BarChart3;
              return (
                <span key={cat} className="inline-flex items-center space-x-0.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-500 border border-gray-200">
                  <CatIcon className="h-2.5 w-2.5" />
                  <span>{count}</span>
                </span>
              );
            })}
          </div>
        )}

        {/* Claims status indicator (MVP Feature 4) */}
        {article.claims_status && article.claims_status !== "completed" && (() => {
          const cfg = CLAIMS_STATUS_CONFIG[article.claims_status] || CLAIMS_STATUS_CONFIG.pending;
          const StatusIcon = cfg.icon;
          return (
            <div className={clsx("flex items-center space-x-1.5 px-2.5 py-1.5 rounded-md border text-xs mb-4", cfg.bg)}>
              <StatusIcon className={clsx("h-3.5 w-3.5", cfg.color, article.claims_status === "processing" && "animate-spin")} />
              <span className={cfg.color}>{cfg.label}</span>
              {article.claims_error_message && (
                <span className="text-gray-400 ml-1 truncate max-w-[180px]">— {article.claims_error_message}</span>
              )}
            </div>
          );
        })()}

        <div className="pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              <span className="font-medium">{article.claim_count}</span> claims assessed
            </div>

            {article.claim_count > 0 && (
              <div className="flex items-center space-x-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2 w-32">
                  <div
                    className="bg-gradient-to-r from-clilens-primary to-clilens-teal-600 h-2 rounded-full transition-all"
                    style={{ width: `${verificationRate}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-clilens-teal-600">{verificationRate}%</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}

export default ArticleCard;
