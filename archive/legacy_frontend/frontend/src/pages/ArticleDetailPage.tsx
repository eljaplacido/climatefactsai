import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Calendar, User, ExternalLink, Shield, Info, Tag, MessageSquare } from "lucide-react";
import { format } from "date-fns";
import { enGB } from "date-fns/locale";
import FactCheckDetail from "../components/FactCheckDetail";
import LoadingSpinner from "../components/LoadingSpinner";
import { api } from "../services/api";
import type { ArticleDetail, FeedbackSummary, FeedbackType } from "../types";

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

function ArticleDetailPage() {
  const { articleId } = useParams<{ articleId: string }>();
  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackSummary, setFeedbackSummary] = useState<FeedbackSummary | null>(null);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [feedbackComment, setFeedbackComment] = useState("");

  useEffect(() => {
    if (articleId) {
      loadArticle(articleId);
    }
  }, [articleId]);

  const loadArticle = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getArticleDetail(id);
      setArticle(data);

      try {
        const feedback = await api.getFeedbackSummary(id);
        setFeedbackSummary(feedback);
      } catch (summaryError) {
        console.warn("Feedback summary unavailable:", summaryError);
        setFeedbackSummary(null);
      }
    } catch (err: any) {
      setError(err.response?.status === 404 ? "Article not found" : "Failed to load article");
      console.error("Error loading article:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (feedback_type: FeedbackType) => {
    if (!articleId) return;
    setFeedbackSubmitting(true);
    setFeedbackError(null);
    setFeedbackMessage(null);

    try {
      await api.submitFeedback(articleId, {
        feedback_type,
        reliability_score: article?.reliability_score,
        comment: feedbackComment.trim() || undefined,
      });
      setFeedbackMessage("Thank you for the feedback!");
      setFeedbackComment("");
      const updated = await api.getFeedbackSummary(articleId);
      setFeedbackSummary(updated);
    } catch (submissionError: any) {
      console.error("Feedback submission failed:", submissionError);
      setFeedbackError("We could not save your feedback. Please try again.");
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const formatDate = (date?: string) => {
    if (!date) return null;
    try {
      return format(new Date(date), "dd MMM yyyy", { locale: enGB });
    } catch (err) {
      console.warn("Invalid date", date, err);
      return date;
    }
  };

  if (loading) {
    return <LoadingSpinner text="Loading article..." />;
  }

  if (error || !article) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
        <p className="text-red-600 text-lg mb-4">{error || "Article not found"}</p>
        <Link to="/" className="text-climate-green-600 hover:underline">
          Back to homepage
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        to="/"
        className="inline-flex items-center space-x-2 text-gray-600 hover:text-climate-green-600 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        <span className="font-medium">Back to articles</span>
      </Link>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <Shield className="h-5 w-5" />
            <span className="text-sm font-medium text-gray-900">{article.source_name}</span>
            <span className="text-sm text-gray-400">•</span>
            <span className="text-sm font-semibold">
              Source score: {article.source_credibility_score}/100
            </span>
            {typeof article.reliability_score === "number" && (
              <span className="text-sm text-gray-600">
                Article score: {article.reliability_score}/100
              </span>
            )}
          </div>
          <span className="text-sm text-gray-500">Language: {article.language_code?.toUpperCase()}</span>
        </div>

        <h1 className="text-3xl font-bold text-gray-900 mb-4 leading-tight">{article.title}</h1>

        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 mb-6">
          {formatDate(article.published_date) && (
            <span className="inline-flex items-center space-x-2">
              <Calendar className="h-4 w-4" />
              <span>{formatDate(article.published_date)}</span>
            </span>
          )}
          {article.author && (
            <span className="inline-flex items-center space-x-2">
              <User className="h-4 w-4" />
              <span>{article.author}</span>
            </span>
          )}
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-2 text-climate-blue-600 hover:text-climate-blue-800"
          >
            <ExternalLink className="h-4 w-4" />
            <span>Open original article</span>
          </a>
        </div>

        {article.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-6">
            {article.tags.map((tag) => (
              <span key={tag} className="inline-flex items-center space-x-1 bg-gray-100 text-gray-700 px-3 py-1 rounded-full text-xs">
                <Tag className="h-3 w-3" />
                <span>{formatTagLabel(tag)}</span>
              </span>
            ))}
          </div>
        )}

        {article.excerpt && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Summary</h2>
            <p className="text-gray-800 leading-relaxed">{article.excerpt}</p>
          </div>
        )}

        {article.full_text && (
          <div className="mt-8 prose prose-lg max-w-none">
            <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{article.full_text}</p>
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="flex items-center space-x-3 mb-6">
          <Info className="h-6 w-6 text-climate-blue-600" />
          <h2 className="text-2xl font-bold text-gray-900">Fact checks ({article.claims.length})</h2>
        </div>

        {article.claims.length === 0 ? (
          <p className="text-gray-500">No claims available for fact-checking.</p>
        ) : (
          <div className="space-y-4">
            {article.claims.map((claim) => (
              claim.fact_check ? (
                <FactCheckDetail
                  key={claim.claim_id}
                  claim={claim.claim_text}
                  status={claim.fact_check.verification_status}
                  confidence={claim.fact_check.confidence_score}
                  justification={claim.fact_check.justification ?? ""}
                  evidence={claim.fact_check.evidence}
                />
              ) : (
                <div key={claim.claim_id} className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-gray-700 mb-2">"{claim.claim_text}"</p>
                  <p className="text-sm text-gray-500 italic">Fact-check queued.</p>
                </div>
              )
            ))}
          </div>
        )}
      </div>

      <div className="bg-gradient-to-r from-climate-green-50 to-climate-blue-50 rounded-xl border border-climate-green-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Overview</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-gray-600">Overall credibility</p>
            <p className="text-2xl font-bold text-climate-green-700">
              {article.overall_credibility === "HIGH"
                ? "High"
                : article.overall_credibility === "MEDIUM"
                ? "Medium"
                : "Low"}
            </p>
          </div>
          <div>
            <p className="text-gray-600">Verified claims</p>
            <p className="text-2xl font-bold text-climate-green-700">
              {article.claims.filter((c) => c.fact_check?.verification_status === "VERIFIED").length} / {article.claims.length}
            </p>
          </div>
          <div>
            <p className="text-gray-600">Source score</p>
            <p className="text-2xl font-bold text-climate-green-700">{article.source_credibility_score}/100</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="flex items-center space-x-3 mb-4">
          <MessageSquare className="h-5 w-5 text-climate-blue-600" />
          <h3 className="text-xl font-semibold text-gray-900">Reader feedback</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 text-sm">
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-500">Responses</p>
            <p className="text-2xl font-bold text-gray-900">{feedbackSummary?.total_feedback ?? 0}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-500">Marked useful</p>
            <p className="text-2xl font-bold text-gray-900">{feedbackSummary?.useful ?? 0}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-500">Average score</p>
            <p className="text-2xl font-bold text-gray-900">
              {feedbackSummary?.average_reliability ? `${feedbackSummary.average_reliability.toFixed(0)}/100` : "-"}
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleFeedback("USEFUL")}
              disabled={feedbackSubmitting}
              className="px-4 py-2 bg-climate-green-600 text-white rounded-lg hover:bg-climate-green-700 transition-colors disabled:opacity-50"
            >
              Mark as helpful
            </button>
            <button
              onClick={() => handleFeedback("NOT_USEFUL")}
              disabled={feedbackSubmitting}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors disabled:opacity-50"
            >
              Not helpful
            </button>
            <button
              onClick={() => handleFeedback("FLAGGED")}
              disabled={feedbackSubmitting}
              className="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors disabled:opacity-50"
            >
              Report an issue
            </button>
          </div>

          <textarea
            value={feedbackComment}
            onChange={(e) => setFeedbackComment(e.target.value)}
            placeholder="Add an optional comment"
            className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-climate-green-500 focus:border-transparent"
            rows={3}
          />

          {feedbackMessage && <p className="text-sm text-green-600">{feedbackMessage}</p>}
          {feedbackError && <p className="text-sm text-red-600">{feedbackError}</p>}
        </div>
      </div>
    </div>
  );
}

export default ArticleDetailPage;
