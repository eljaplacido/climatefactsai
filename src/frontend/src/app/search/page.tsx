"use client";

import { useEffect, useMemo, useState } from "react";
import ArticleCard from "@/components/ArticleCard";
import CountrySelector from "@/components/CountrySelector";
import { api } from "@/lib/api";
import type { Article, TagStat, SearchSuggestion } from "@/types";
import { Globe, Tag as TagIcon, Newspaper, Search as SearchIcon, Calendar, X } from "lucide-react";
import LoginPrompt from "@/components/LoginPrompt";
import { useAuth } from "@/lib/auth";
import { useUrlState, URL_STATE_SERIALIZERS } from "@/lib/useUrlState";

type Credibility = "ALL" | "HIGH" | "MEDIUM" | "LOW";

// Phase 2H (2026-05-23) — MH1 rollout. The most-shareable filters go into
// the URL so a colleague can paste a search link and land on the same view.
// Tags (array) and source (typeahead-driven) stay session-local for v1.
const credibilitySerializer = {
  encode: (v: Credibility) => (v === "ALL" ? null : v),
  decode: (raw: string | null): Credibility => {
    const valid: Credibility[] = ["ALL", "HIGH", "MEDIUM", "LOW"];
    return (valid.find((k) => k === raw) ?? "ALL") as Credibility;
  },
};

const CONTENT_CATEGORIES = [
  { value: "climate_science", label: "Climate Science" },
  { value: "sustainability", label: "Sustainability" },
  { value: "policy", label: "Policy" },
  { value: "green_transition", label: "Green Transition" },
  { value: "circular_economy", label: "Circular Economy" },
  { value: "localized_forecast", label: "Local Forecast" },
] as const;

export default function SearchPage() {
  const { isLoggedIn } = useAuth();
  // Phase 2H (2026-05-23) — URL-persistent state for the shareable filter set.
  const [q, setQ] = useUrlState("q", "", URL_STATE_SERIALIZERS.string);
  const [country, setCountry] = useUrlState<string | null>(
    "country",
    null,
    URL_STATE_SERIALIZERS.nullableString,
  );
  const [credibility, setCredibility] = useUrlState<Credibility>(
    "credibility",
    "ALL",
    credibilitySerializer,
  );
  const [tags, setTags] = useState<string[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [source, setSource] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionIndex, setSuggestionIndex] = useState<number>(-1);
  const [suggestionFilter, setSuggestionFilter] = useState<"all" | "tag" | "country" | "source">("all");
  const [tagStats, setTagStats] = useState<TagStat[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Date range filter — URL-persistent (typing in date inputs commits on change).
  const [dateFrom, setDateFrom] = useUrlState("from", "", URL_STATE_SERIALIZERS.string);
  const [dateTo, setDateTo] = useUrlState("to", "", URL_STATE_SERIALIZERS.string);

  // Content category filter — URL-persistent.
  const [contentCategory, setContentCategory] = useUrlState(
    "category",
    "",
    URL_STATE_SERIALIZERS.string,
  );

  // Debounce query input
  const [debouncedQ, setDebouncedQ] = useState(q);
  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(q.trim()), 300);
    return () => clearTimeout(id);
  }, [q]);

  const filtersSummary = useMemo(() => {
    const parts: string[] = [];
    if (debouncedQ) parts.push(`"${debouncedQ}"`);
    if (country) parts.push(`country: ${country}`);
    if (credibility !== "ALL") parts.push(`credibility: ${credibility}`);
    if (tags.length) parts.push(`tags: ${tags.join(", ")}`);
    if (source) parts.push(`source: ${source}`);
    if (dateFrom) parts.push(`from: ${dateFrom}`);
    if (dateTo) parts.push(`to: ${dateTo}`);
    if (contentCategory) {
      const catLabel = CONTENT_CATEGORIES.find((c) => c.value === contentCategory)?.label || contentCategory;
      parts.push(`category: ${catLabel}`);
    }
    return parts.join(" \u00b7 ") || "All articles";
  }, [debouncedQ, country, credibility, tags, source, dateFrom, dateTo, contentCategory]);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (country) count++;
    if (credibility !== "ALL") count++;
    if (tags.length) count++;
    if (dateFrom || dateTo) count++;
    if (contentCategory) count++;
    if (source) count++;
    return count;
  }, [country, credibility, tags, dateFrom, dateTo, contentCategory, source]);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.getArticles({
          limit: 20,
          country: country ?? undefined,
          credibility: credibility === "ALL" ? undefined : credibility,
          tags: tags.length ? tags : undefined,
          source: source ?? undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          category: contentCategory || undefined,
          // Backend supports q filter (full-text on title + excerpt)
          // @ts-ignore
          q: debouncedQ || undefined,
        } as any);
        setArticles(res || []);
      } catch (e) {
        console.error("Search failed", e);
        setError("Search unavailable. Check API and try again.");
      } finally {
        setLoading(false);
      }
    };
    fetchResults();
  }, [debouncedQ, country, credibility, tags, source, dateFrom, dateTo, contentCategory]);

  // Load tag stats when country changes
  useEffect(() => {
    const loadTags = async () => {
      try {
        const data = await api.getTagStats(country ?? undefined);
        setTagStats(data.slice(0, 16));
      } catch (e) {
        // ignore for now
      }
    };
    loadTags();
  }, [country]);

  // Load suggestions when query changes
  useEffect(() => {
    const load = async () => {
      if (!debouncedQ || debouncedQ.length < 2) { setSuggestions([]); setSuggestionIndex(-1); return; }
      try {
        const categoryParam = suggestionFilter === "all" ? undefined : suggestionFilter;
        const s = await api.getSearchSuggestions(debouncedQ, categoryParam as any, 8);
        setSuggestions(s);
        setSuggestionIndex(s.length > 0 ? 0 : -1);
      } catch (e) {
        setSuggestions([]);
        setSuggestionIndex(-1);
      }
    };
    load();
  }, [debouncedQ, suggestionFilter]);

  const toggleTag = (tag: string) => {
    setTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
  };

  const clearAllFilters = () => {
    setQ("");
    setCountry(null);
    setCredibility("ALL");
    setTags([]);
    setSource(null);
    setDateFrom("");
    setDateTo("");
    setContentCategory("");
  };

  const onSelectSuggestion = (s: SearchSuggestion) => {
    if (s.category === "tag") {
      toggleTag(s.text);
    } else if (s.category === "country") {
      setQ(s.text);
    } else if (s.category === "source") {
      setSource(s.text);
    } else {
      setQ(s.text);
    }
    setShowSuggestions(false);
    setSuggestionIndex(-1);
  };

  const onInputKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSuggestionIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSuggestionIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (suggestionIndex >= 0 && suggestionIndex < suggestions.length) {
        onSelectSuggestion(suggestions[suggestionIndex]);
      }
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
      setSuggestionIndex(-1);
    }
  };

  const renderSuggestionIcon = (category: string) => {
    switch (category) {
      case "tag":
        return <TagIcon className="h-4 w-4 text-gray-500" />;
      case "country":
        return <Globe className="h-4 w-4 text-gray-500" />;
      case "source":
        return <Newspaper className="h-4 w-4 text-gray-500" />;
      default:
        return <SearchIcon className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <section className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-bold text-gray-900">Search</h1>
            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="text-sm text-gray-500 hover:text-red-600 flex items-center gap-1"
              >
                <X className="h-3.5 w-3.5" />
                Clear all filters ({activeFilterCount})
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
            <div className="lg:col-span-3">
              <div className="relative">
                <input
                  value={q}
                  onChange={(e) => { setQ(e.target.value); setShowSuggestions(true); }}
                  onKeyDown={onInputKeyDown}
                  onFocus={() => { if (q.trim().length >= 2) setShowSuggestions(true); }}
                  onBlur={() => { setTimeout(() => setShowSuggestions(false), 200); }}
                  placeholder="Search topics, titles, keywords..."
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent bg-white"
                  aria-label="Search query"
                />
                <svg className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                {showSuggestions && (
                  <div className="absolute z-20 mt-2 w-full bg-white border border-gray-200 rounded-lg shadow-lg">
                    {/* Category filter tabs */}
                    <div className="flex items-center gap-1 px-2 pt-2 pb-1 border-b border-gray-100 text-xs">
                      {(["all","tag","country","source"] as const).map((cat) => (
                        <button
                          key={cat}
                          type="button"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => setSuggestionFilter(cat)}
                          className={`px-2 py-1 rounded ${suggestionFilter===cat?"bg-clilens-teal-50 text-clilens-teal-700":"text-gray-600 hover:bg-gray-50"}`}
                        >
                          {cat === "all" ? "All" : cat.charAt(0).toUpperCase()+cat.slice(1)}
                        </button>
                      ))}
                    </div>
                    <div className="max-h-64 overflow-auto">
                      {suggestions.length === 0 && debouncedQ.length >= 2 ? (
                        <div className="px-3 py-3 text-sm text-gray-500">No suggestions</div>
                      ) : (
                        suggestions.map((s, i) => (
                          <button
                            key={`${s.category}-${s.text}-${i}`}
                            className={`w-full text-left px-3 py-2 flex items-center justify-between ${i===suggestionIndex?"bg-gray-100":"hover:bg-gray-50"}`}
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => onSelectSuggestion(s)}
                            type="button"
                          >
                            <span className="flex items-center gap-2 text-sm text-gray-800">
                              {renderSuggestionIcon(s.category)}
                              {s.text}
                            </span>
                            <span className="text-xs text-gray-500">{s.category} &bull; {s.count}</span>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-2">{filtersSummary}</p>

              {/* Content category pills (inline, below search) */}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-gray-500">Category:</span>
                <button
                  type="button"
                  onClick={() => setContentCategory("")}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                    contentCategory === ""
                      ? "bg-clilens-primary text-white border-clilens-primary"
                      : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
                  }`}
                >
                  All
                </button>
                {CONTENT_CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    onClick={() => setContentCategory(contentCategory === cat.value ? "" : cat.value)}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                      contentCategory === cat.value
                        ? "bg-clilens-primary text-white border-clilens-primary"
                        : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <CountrySelector value={country} onChange={setCountry} />

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Credibility</label>
                <select
                  value={credibility}
                  onChange={(e) => setCredibility(e.target.value as Credibility)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 bg-white focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
                >
                  <option value="ALL">All</option>
                  <option value="HIGH">High</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="LOW">Low</option>
                </select>
              </div>

              {/* Date range filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Calendar className="inline h-4 w-4 mr-1" />
                  Date Range
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">From</label>
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={(e) => setDateFrom(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">To</label>
                    <input
                      type="date"
                      value={dateTo}
                      onChange={(e) => setDateTo(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
                    />
                  </div>
                </div>
                {(dateFrom || dateTo) && (
                  <button
                    type="button"
                    onClick={() => { setDateFrom(""); setDateTo(""); }}
                    className="mt-1 text-xs text-gray-500 hover:text-red-600"
                  >
                    Clear dates
                  </button>
                )}
              </div>

              {/* Tags with clickable pills */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <TagIcon className="inline h-4 w-4 mr-1" />
                  Tags / Themes
                </label>
                <input
                  placeholder="e.g. climate_change, esg"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 bg-white focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
                  value={tags.join(", ")}
                  onChange={(e) =>
                    setTags(
                      e.target.value
                        .split(",")
                        .map((t) => t.trim())
                        .filter(Boolean)
                    )
                  }
                />

                {tagStats.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {tagStats.map((t) => (
                      <button
                        key={t.tag}
                        type="button"
                        onClick={() => toggleTag(t.tag)}
                        className={`px-2 py-1 rounded-full text-xs border ${
                          tags.includes(t.tag)
                            ? "bg-clilens-teal-50 text-clilens-teal-700 border-clilens-teal-200"
                            : "bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100"
                        }`}
                        aria-pressed={tags.includes(t.tag)}
                      >
                        {t.tag} ({t.article_count})
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {!isLoggedIn && (
            <div className="mt-4 max-w-3xl">
              <LoginPrompt />
            </div>
          )}
        </div>
      </section>

      <section>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Results count */}
          {!loading && !error && (
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-600">
                {articles.length} result{articles.length !== 1 ? "s" : ""}
              </p>
            </div>
          )}

          {loading && (
            // Skeleton grid matching ArticleCard footprint so the page doesn't
            // collapse to a one-line "Loading…" while results stream. Mirrors
            // the home-page skeleton pattern.
            <div className="grid gap-6 md:grid-cols-2" aria-busy="true" aria-label="Loading search results">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-lg border border-gray-200 bg-white p-5 animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-3/4 mb-3"></div>
                  <div className="h-3 bg-gray-200 rounded w-full mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded w-5/6 mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded w-2/3 mb-4"></div>
                  <div className="flex gap-2">
                    <div className="h-5 bg-gray-200 rounded w-16"></div>
                    <div className="h-5 bg-gray-200 rounded w-20"></div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {error && (
            <div className="text-red-600 mb-4">{error}</div>
          )}
          {!loading && !error && articles.length > 0 && (
            <div className="grid gap-6 md:grid-cols-2">
              {articles.map((a) => (
                <ArticleCard key={a.article_id} article={a} />
              ))}
            </div>
          )}
          {!loading && !error && articles.length === 0 && (
            <div className="text-center py-12">
              <SearchIcon className="h-8 w-8 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No results found. Try adjusting your filters.</p>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
