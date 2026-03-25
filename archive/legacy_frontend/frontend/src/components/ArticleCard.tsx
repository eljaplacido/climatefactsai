import { useState } from "react";
import { Link } from "react-router-dom";
import { Calendar, User, CheckCircle, AlertTriangle, Shield, HelpCircle } from "lucide-react";
import { format } from "date-fns";
import { enGB } from "date-fns/locale";
import clsx from "clsx";
import type { Article } from "../types";

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

const getCredibilityConfig = (credibility: string) => {
  switch (credibility) {
    case "HIGH":
      return {
        bg: "bg-green-50",
        text: "text-green-700",
        border: "border-green-200",
        icon: CheckCircle,
        label: "High credibility",
      };
    case "MEDIUM":
      return {
        bg: "bg-yellow-50",
        text: "text-yellow-700",
        border: "border-yellow-200",
        icon: Shield,
        label: "Moderate credibility",
      };
    case "LOW":
      return {
        bg: "bg-red-50",
        text: "text-red-700",
        border: "border-red-200",
        icon: AlertTriangle,
        label: "Low credibility",
      };
    default:
      return {
        bg: "bg-gray-50",
        text: "text-gray-700",
        border: "border-gray-200",
        icon: Shield,
        label: "Not yet rated",
      };
  }
};

function ArticleCard({ article }: ArticleCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  const credConfig = getCredibilityConfig(article.overall_credibility);
  const CredibilityIcon = credConfig.icon;

  const verificationRate = article.claim_count > 0
    ? Math.round((article.verified_claim_count / article.claim_count) * 100)
    : 0;

  return (
    <Link
      to={`/articles/${article.article_id}`}
      className="block bg-white rounded-xl shadow-sm hover:shadow-md transition-all duration-200 border border-gray-200 overflow-hidden group"
    >
      <div className="p-6">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <span className="text-sm font-medium text-gray-900">{article.source_name}</span>
          </div>

          <div className="relative">
            <div
              className={clsx(
                "flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-medium border cursor-help",
                credConfig.bg,
                credConfig.text,
                credConfig.border
              )}
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
            >
              <CredibilityIcon className="h-3.5 w-3.5" />
              <span>{credConfig.label}</span>
              <HelpCircle className="h-3 w-3 opacity-60" />
            </div>

            {showTooltip && (
              <div className="absolute right-0 top-full mt-2 w-72 bg-gray-900 text-white text-xs rounded-lg p-3 shadow-xl z-10">
                <p className="font-semibold mb-1">Reliability score: {article.source_credibility_score}/100</p>
                <p className="text-gray-300 mb-2">
                  {article.source_credibility_score >= 80 && "Highly trusted source recognised for rigorous journalism."}
                  {article.source_credibility_score >= 60 && article.source_credibility_score < 80 && "Generally reliable source with occasional viewpoint bias."}
                  {article.source_credibility_score < 60 && "Reliability uncertain. Cross-check key claims with additional sources."}
                </p>
                <p className="text-xs text-gray-400">Based on: source history, editorial standards, fact-checking record.</p>
                <div className="absolute -top-2 right-4 w-4 h-4 bg-gray-900 rotate-45"></div>
              </div>
            )}
          </div>
        </div>

        <h3 className="text-xl font-bold text-gray-900 mb-3 group-hover:text-climate-green-600 transition-colors line-clamp-2">
          {article.title}
        </h3>

        {article.excerpt && (
          <p className="text-gray-600 text-sm mb-4 line-clamp-3">
            {article.excerpt}
          </p>
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

          {typeof article.reliability_score === "number" && (
            <div className="flex items-center space-x-1">
              <Shield className="h-4 w-4" />
              <span>Reliability {article.reliability_score}/100</span>
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              <span className="font-medium">{article.claim_count}</span> claims assessed
            </div>

            {article.claim_count > 0 && (
              <div className="flex items-center space-x-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2 w-32">
                  <div
                    className="bg-gradient-to-r from-climate-green-500 to-climate-green-600 h-2 rounded-full transition-all"
                    style={{ width: `${verificationRate}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-climate-green-600">{verificationRate}%</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}

export default ArticleCard;
