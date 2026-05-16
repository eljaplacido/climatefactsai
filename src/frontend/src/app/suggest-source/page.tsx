"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Lightbulb,
  Globe,
  Send,
  Loader2,
  CheckCircle,
  Clock,
  XCircle,
  Eye,
  ExternalLink,
  LogIn,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const SOURCE_TYPES = [
  { value: "news", label: "News" },
  { value: "climate_data", label: "Climate Data" },
  { value: "research", label: "Research" },
  { value: "weather_api", label: "Weather API" },
  { value: "government", label: "Government" },
];

const COUNTRIES = [
  { code: "", label: "Select country (optional)" },
  { code: "FI", label: "Finland" },
  { code: "SE", label: "Sweden" },
  { code: "NO", label: "Norway" },
  { code: "DK", label: "Denmark" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "NL", label: "Netherlands" },
  { code: "GB", label: "United Kingdom" },
  { code: "US", label: "United States" },
  { code: "EU", label: "European Union" },
  { code: "IT", label: "Italy" },
  { code: "ES", label: "Spain" },
  { code: "PL", label: "Poland" },
  { code: "AT", label: "Austria" },
  { code: "BE", label: "Belgium" },
  { code: "CH", label: "Switzerland" },
  { code: "IE", label: "Ireland" },
  { code: "PT", label: "Portugal" },
];

const LANGUAGES = [
  { code: "", label: "Select language (optional)" },
  { code: "en", label: "English" },
  { code: "fi", label: "Finnish" },
  { code: "sv", label: "Swedish" },
  { code: "no", label: "Norwegian" },
  { code: "da", label: "Danish" },
  { code: "de", label: "German" },
  { code: "fr", label: "French" },
  { code: "nl", label: "Dutch" },
  { code: "es", label: "Spanish" },
  { code: "it", label: "Italian" },
  { code: "pl", label: "Polish" },
  { code: "pt", label: "Portuguese" },
];

interface Suggestion {
  suggestion_id: string;
  url: string;
  source_type: string;
  name: string;
  description?: string;
  country_code?: string;
  language?: string;
  status: string;
  admin_notes?: string;
  created_at?: string;
  reviewed_at?: string;
}

const STATUS_CONFIG: Record<string, { color: string; bg: string; icon: typeof Clock; label: string }> = {
  pending: { color: "text-yellow-700", bg: "bg-yellow-100", icon: Clock, label: "Pending" },
  reviewing: { color: "text-blue-700", bg: "bg-blue-100", icon: Eye, label: "Reviewing" },
  approved: { color: "text-green-700", bg: "bg-green-100", icon: CheckCircle, label: "Approved" },
  rejected: { color: "text-red-700", bg: "bg-red-100", icon: XCircle, label: "Rejected" },
};

export default function SuggestSourcePage() {
  const router = useRouter();
  const { user, isLoggedIn, loading: authLoading, token } = useAuth();

  // Form state
  const [url, setUrl] = useState("");
  const [sourceType, setSourceType] = useState("news");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [language, setLanguage] = useState("");

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ suggestion_id: string; message: string } | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // My suggestions
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // Load user's suggestions
  useEffect(() => {
    if (isLoggedIn && token) {
      loadMySuggestions();
    }
  }, [isLoggedIn, token]);

  async function loadMySuggestions() {
    setLoadingSuggestions(true);
    try {
      const resp = await fetch(`${API_URL}/api/source-suggestions/my`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        setSuggestions(await resp.json());
      }
    } catch {
      // Silently fail — suggestions list is supplementary
    } finally {
      setLoadingSuggestions(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setSubmitResult(null);

    try {
      const body: Record<string, string> = {
        url,
        source_type: sourceType,
        name,
        description,
      };
      if (countryCode) body.country_code = countryCode;
      if (language) body.language = language;

      const resp = await fetch(`${API_URL}/api/source-suggestions/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Submission failed");
      }

      setSubmitResult({ suggestion_id: data.suggestion_id, message: data.message });

      // Reset form
      setUrl("");
      setName("");
      setDescription("");
      setCountryCode("");
      setLanguage("");

      // Refresh suggestions list
      loadMySuggestions();
    } catch (err: any) {
      setSubmitError(err.message || "Failed to submit suggestion");
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-teal-600" />
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-md border border-gray-200 p-8 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-teal-100 rounded-full mb-4">
            <Lightbulb className="h-7 w-7 text-teal-600" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Sign in to suggest a source</h1>
          <p className="text-sm text-gray-600 mb-6">
            We track who suggests each source so we can credit you when it ships and follow up if we need clarification.
          </p>
          <div className="flex flex-col sm:flex-row gap-2 justify-center">
            <Link
              href="/login?redirect=/suggest-source"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
            >
              <LogIn className="h-4 w-4" /> Sign in
            </Link>
            <Link
              href="/signup?redirect=/suggest-source"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-white text-teal-700 border border-teal-200 rounded-lg text-sm font-medium hover:bg-teal-50 transition-colors"
            >
              Create account
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <Lightbulb className="h-5 w-5 text-teal-600" />
            <h1 className="text-xl font-bold text-gray-900">Suggest a Source</h1>
          </div>
          <p className="mt-2 text-sm text-gray-500 ml-9">
            Help us grow our climate intelligence coverage by suggesting new sources
          </p>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* Submission Form */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Submit a New Source</h2>

          {submitResult && (
            <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-green-800">{submitResult.message}</p>
                <p className="text-xs text-green-600 mt-1">
                  Suggestion ID: <code className="bg-green-100 px-1 py-0.5 rounded">{submitResult.suggestion_id}</code>
                </p>
              </div>
            </div>
          )}

          {submitError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {submitError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* URL */}
            <div>
              <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-1">
                Source URL <span className="text-red-500">*</span>
              </label>
              <input
                id="url"
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/climate-data"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
              />
            </div>

            {/* Source Type */}
            <div>
              <label htmlFor="sourceType" className="block text-sm font-medium text-gray-700 mb-1">
                Source Type <span className="text-red-500">*</span>
              </label>
              <select
                id="sourceType"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none bg-white"
              >
                {SOURCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                Source Name <span className="text-red-500">*</span>
              </label>
              <input
                id="name"
                type="text"
                required
                maxLength={200}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Finnish Meteorological Institute Open Data"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                Why is this source valuable? <span className="text-red-500">*</span>
              </label>
              <textarea
                id="description"
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what kind of data or content this source provides and why it would be useful for climate intelligence..."
                rows={4}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none resize-y"
              />
            </div>

            {/* Country and Language row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="country" className="block text-sm font-medium text-gray-700 mb-1">
                  Country
                </label>
                <select
                  id="country"
                  value={countryCode}
                  onChange={(e) => setCountryCode(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none bg-white"
                >
                  {COUNTRIES.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="language" className="block text-sm font-medium text-gray-700 mb-1">
                  Language
                </label>
                <select
                  id="language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none bg-white"
                >
                  {LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting || !url || !name || !description}
              className="w-full py-3 bg-teal-600 text-white rounded-lg font-medium hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" /> Submitting...
                </>
              ) : (
                <>
                  <Send className="h-5 w-5" /> Submit Suggestion
                </>
              )}
            </button>
          </form>
        </div>

        {/* My Suggestions — only visible when logged in */}
        {isLoggedIn && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">My Suggestions</h2>

            {loadingSuggestions ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : suggestions.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-8">
                You have not submitted any source suggestions yet.
              </p>
            ) : (
              <div className="space-y-3">
                {suggestions.map((s) => {
                  const cfg = STATUS_CONFIG[s.status] || STATUS_CONFIG.pending;
                  const StatusIcon = cfg.icon;
                  return (
                    <div
                      key={s.suggestion_id}
                      className="border border-gray-100 rounded-lg p-4 hover:border-gray-200 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-sm font-semibold text-gray-900 truncate">
                              {s.name}
                            </h3>
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color}`}
                            >
                              <StatusIcon className="h-3 w-3" />
                              {cfg.label}
                            </span>
                          </div>
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-teal-600 hover:text-teal-800 flex items-center gap-1 truncate"
                          >
                            <ExternalLink className="h-3 w-3 flex-shrink-0" />
                            {s.url}
                          </a>
                          {s.description && (
                            <p className="mt-1 text-xs text-gray-500 line-clamp-2">{s.description}</p>
                          )}
                          {s.admin_notes && (
                            <p className="mt-1 text-xs text-slate-600 bg-slate-50 px-2 py-1 rounded">
                              Admin: {s.admin_notes}
                            </p>
                          )}
                        </div>
                        <div className="text-right flex-shrink-0">
                          <span className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded">
                            {s.source_type.replace("_", " ")}
                          </span>
                          {s.created_at && (
                            <p className="text-[10px] text-gray-400 mt-1">
                              {new Date(s.created_at).toLocaleDateString()}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
