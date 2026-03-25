import { useState, useEffect } from "react";
import clsx from "clsx";
import { Filter, TrendingUp, Tag as TagIcon, Newspaper, CheckCircle, BarChart3, Clock } from "lucide-react";
import ArticleCard from "../components/ArticleCard";
import StatCard from "../components/StatCard";
import LoadingSpinner from "../components/LoadingSpinner";
import CountrySelector from "../components/CountrySelector";
import { api } from "../services/api";
import type { Article, DashboardStats, TagStat } from "../types";

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

function HomePage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [availableTags, setAvailableTags] = useState<TagStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "HIGH" | "MEDIUM" | "LOW">("ALL");
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  useEffect(() => {
    loadData();
  }, [filter, selectedCountry, selectedSource, selectedTags]);

  useEffect(() => {
    loadTags();
  }, [selectedCountry]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [articlesData, statsData] = await Promise.all([
        api.getArticles({
          limit: 20,
          credibility: filter === "ALL" ? undefined : filter,
          country: selectedCountry || undefined,
          source: selectedSource || undefined,
          tags: selectedTags.length ? selectedTags : undefined,
        }),
        api.getStats(),
      ]);

      setArticles(articlesData);
      setStats(statsData);
    } catch (error) {
      console.error("Error loading data:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadTags = async () => {
    try {
      const tags = await api.getTagStats(selectedCountry || undefined);
      setAvailableTags(tags);
      setSelectedTags((current) => current.filter((tag) => tags.some((t) => t.tag === tag)));
    } catch (error) {
      console.error("Error loading tags:", error);
    }
  };

  const handleTagToggle = (tag: string) => {
    setSelectedTags((current) =>
      current.includes(tag)
        ? current.filter((t) => t !== tag)
        : [...current, tag]
    );
  };

  return (
    <div className="space-y-8">
      <div className="bg-gradient-to-r from-climate-green-600 to-climate-blue-600 rounded-2xl p-8 text-white shadow-lg">
        <div className="max-w-3xl">
          <h1 className="text-4xl font-bold mb-4">Climate News Europe</h1>
          <p className="text-lg text-white/90 mb-6">
            Fact-checked climate reporting across Europe. Pick a country to see the latest developments
            with transparent verification powered by AI.
          </p>
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-5 w-5" />
              <span>Verified stories</span>
            </div>
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-5 w-5" />
              <span>30+ European markets</span>
            </div>
          </div>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard title="Total articles" value={stats.total_articles} icon={Newspaper} color="blue" />
          <StatCard title="Published today" value={stats.articles_today} icon={Clock} color="green" />
          <StatCard title="Fact checks" value={stats.total_fact_checks} icon={CheckCircle} color="purple" />
          <StatCard
            title="Average confidence"
            value={`${stats.average_confidence.toFixed(0)}%`}
            icon={BarChart3}
            color="orange"
          />
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center space-x-2 mb-4">
          <Filter className="h-5 w-5 text-gray-500" />
          <span className="font-medium text-gray-700">Filter stories</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <CountrySelector value={selectedCountry} onChange={setSelectedCountry} />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Source</label>
            <select
              value={selectedSource || ""}
              onChange={(e) => setSelectedSource(e.target.value || null)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 bg-white focus:ring-2 focus:ring-climate-green-500 focus:border-transparent"
            >
              <option value="">All sources</option>
              <option value="YLE">Yle (Finland)</option>
              <option value="Helsingin Sanomat">Helsingin Sanomat (Finland)</option>
              <option value="SVT">SVT (Sweden)</option>
              <option value="NRK">NRK (Norway)</option>
              <option value="BBC">BBC (UK)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Credibility</label>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as typeof filter)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 bg-white focus:ring-2 focus:ring-climate-green-500 focus:border-transparent"
            >
              <option value="ALL">All</option>
              <option value="HIGH">High (≥80%)</option>
              <option value="MEDIUM">Medium (50–79%)</option>
              <option value="LOW">Low (&lt;50%)</option>
            </select>
          </div>

          <div>
            <label className="flex items-center text-sm font-medium text-gray-700 mb-2 space-x-2">
              <TagIcon className="h-4 w-4" />
              <span>Tags</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {availableTags.slice(0, 10).map((tag) => {
                const isActive = selectedTags.includes(tag.tag);
                return (
                  <button
                    key={tag.tag}
                    type="button"
                    onClick={() => handleTagToggle(tag.tag)}
                    className={clsx(
                      "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                      isActive
                        ? "bg-climate-green-100 text-climate-green-700 border-climate-green-200"
                        : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                    )}
                  >
                    {formatTagLabel(tag.tag)}
                    <span className="ml-1 text-[0.7rem] text-gray-400">{tag.article_count}</span>
                  </button>
                );
              })}
              {availableTags.length === 0 && (
                <span className="text-xs text-gray-400">Tags will appear once articles are available.</span>
              )}
            </div>
          </div>
        </div>

        {(selectedCountry || selectedSource || selectedTags.length > 0) && (
          <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
            <span className="text-sm text-gray-600">Active filters:</span>
            {selectedCountry && (
              <span className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                {selectedCountry}
                <button onClick={() => setSelectedCountry(null)} className="ml-2 font-bold" aria-label="Remove country filter">
                  ×
                </button>
              </span>
            )}
            {selectedSource && (
              <span className="inline-flex items-center px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                {selectedSource}
                <button onClick={() => setSelectedSource(null)} className="ml-2 font-bold" aria-label="Remove source filter">
                  ×
                </button>
              </span>
            )}
            {selectedTags.map((tag) => (
              <span key={tag} className="inline-flex items-center px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                {formatTagLabel(tag)}
                <button onClick={() => handleTagToggle(tag)} className="ml-2 font-bold" aria-label="Remove tag filter">
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {loading ? (
        <LoadingSpinner text="Loading articles..." />
      ) : articles.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <p className="text-gray-500 text-lg">No articles found for the selected filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {articles.map((article) => (
            <ArticleCard key={article.article_id} article={article} />
          ))}
        </div>
      )}

      {articles.length >= 20 && (
        <div className="flex justify-center">
          <button className="px-6 py-3 bg-climate-green-600 text-white rounded-lg font-medium hover:bg-climate-green-700 transition-colors shadow-sm">
            Load more articles
          </button>
        </div>
      )}
    </div>
  );
}

export default HomePage;
