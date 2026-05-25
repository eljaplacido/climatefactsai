import axios from "axios";
import type {
  Article,
  ArticleDetail,
  DashboardStats,
  WorkflowStatus,
  TagStat,
  FeedbackSummary,
  FeedbackRequestPayload,
  Country,
  SearchSuggestion,
  SearchHistoryEntry,
  AnalyzeUrlResponse,
  SourceProfile,
  ConversationEntry,
  ConversationHistory,
  SimilarArticle,
  ForecastComparison,
  DeepSearchResult,
  CompareResult,
  ArticleWeatherContext,
  LocationWeatherContext,
  AnalyticsDashboard,
  ArticleTrend,
  SourcePerformance,
  PipelineStatus,
} from "../types";
import { generateRequestId, setLastTrace } from "./trace";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const requestId = generateRequestId();
  config.headers = config.headers || {};
  config.headers["X-Request-ID"] = requestId;
  // Attach auth token if available
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("clilens_token");
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  setLastTrace({ requestId });
  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    const requestId =
      (response.config.headers?.["X-Request-ID"] as string | undefined) ||
      (response.headers?.["x-request-id"] as string | undefined);
    const traceId = response.headers?.["x-trace-id"] as string | undefined;
    setLastTrace({ requestId, traceId });
    return response;
  },
  (error) => {
    const requestId = error?.config?.headers?.["X-Request-ID"] as string | undefined;
    const traceId = error?.response?.headers?.["x-trace-id"] as string | undefined;
    setLastTrace({ requestId, traceId });
    return Promise.reject(error);
  }
);

export const api = {
  async getArticles(params?: {
    limit?: number;
    offset?: number;
    date_from?: string;
    date_to?: string;
    credibility?: "HIGH" | "MEDIUM" | "LOW";
    country?: string;
    source?: string;
    tags?: string[];
    category?: string;
  }): Promise<Article[]> {
    const query: Record<string, string | number | string[] | undefined> = {
      limit: params?.limit,
      offset: params?.offset,
      date_from: params?.date_from,
      date_to: params?.date_to,
      credibility: params?.credibility,
      country: params?.country,
      source: params?.source,
      tags: params?.tags,
      category: params?.category,
    };

    const response = await apiClient.get("/api/articles", {
      params: query,
      paramsSerializer: (qp) => {
        const searchParams = new URLSearchParams();
        Object.entries(qp).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            value.forEach((item) => {
              if (item !== undefined) {
                searchParams.append(key, item);
              }
            });
          } else if (value !== undefined && value !== null) {
            searchParams.append(key, String(value));
          }
        });
        return searchParams.toString();
      },
    });

    return response.data;
  },

  async getCountries(): Promise<Country[]> {
    const response = await apiClient.get("/api/countries");
    return response.data;
  },

  async getArticleDetail(articleId: string): Promise<ArticleDetail> {
    const response = await apiClient.get(`/api/articles/${articleId}`);
    return response.data;
  },

  async getStats(): Promise<DashboardStats> {
    const response = await apiClient.get("/api/stats");
    return response.data;
  },

  async getAdminDashboard(): Promise<DashboardStats> {
    const response = await apiClient.get("/api/admin/dashboard");
    return response.data;
  },

  async triggerWorkflow(taskId?: string): Promise<{ task_id: string; status: string; message: string }> {
    const response = await apiClient.post("/api/admin/trigger-workflow", { task_id: taskId });
    return response.data;
  },

  async discoverNews(payload: {
    country_code?: string;
    country_name?: string;
    keywords?: string[];
    max_articles?: number;
    days_back?: number;
    verify?: boolean;
  }): Promise<{ task_id: string; inserted: number; article_ids: string[] }> {
    const response = await apiClient.post("/api/admin/discover-news", payload);
    return response.data;
  },

  async getWorkflows(limit: number = 10): Promise<WorkflowStatus[]> {
    const response = await apiClient.get("/api/admin/workflows", { params: { limit } });
    return response.data;
  },

  async getTagStats(country?: string): Promise<TagStat[]> {
    const response = await apiClient.get("/api/tags", { params: { country } });
    return response.data;
  },

  async getSearchSuggestions(q: string, category?: "tag" | "country" | "source", limit: number = 8): Promise<SearchSuggestion[]> {
    const response = await apiClient.get("/api/search/suggestions", {
      params: { q, category, limit },
    });
    return response.data;
  },

  async getSearchHistory(limit: number = 10): Promise<SearchHistoryEntry[]> {
    try {
      const response = await apiClient.get("/api/search/history", { params: { limit } });
      return response.data;
    } catch {
      return [];
    }
  },

  async submitFeedback(articleId: string, payload: FeedbackRequestPayload) {
    const response = await apiClient.post(`/api/articles/${articleId}/feedback`, payload);
    return response.data;
  },

  async getFeedbackSummary(articleId: string): Promise<FeedbackSummary> {
    const response = await apiClient.get(`/api/articles/${articleId}/feedback`);
    return response.data;
  },

  async analyzeUrl(url: string): Promise<AnalyzeUrlResponse> {
    const response = await apiClient.post('/api/analyze-url', { url });
    return response.data;
  },

  async getAnalysisStatus(jobId: string, accessToken?: string): Promise<AnalyzeUrlResponse> {
    // Anonymous reads MUST pass the access_token returned by POST; authenticated
    // owners can omit it. Backend gates this at /api/analyze-url/{job_id}.
    const params = accessToken ? { token: accessToken } : undefined;
    const response = await apiClient.get(`/api/analyze-url/${jobId}`, { params });
    return response.data;
  },

  async getArticleInsights(articleId: string): Promise<{
    article_id: string;
    reliability_score: number | null;
    credibility_level: string | null;
    decomposed_confidence: any;
    insight_summary: string | null;
    claims_count: number;
    verified_claims_count: number;
    claims_by_category: Record<string, number>;
  }> {
    const response = await apiClient.get(`/api/v2/intelligence/insights/${articleId}`);
    return response.data;
  },

  async analyzeText(text: string, maxClaims: number = 15): Promise<{
    total_claims: number;
    claims_by_category: Record<string, number>;
    claims: Record<string, any[]>;
  }> {
    const response = await apiClient.post("/api/v2/intelligence/analyze-text", {
      text,
      max_claims: maxClaims,
    });
    return response.data;
  },

  async triggerFullAnalysis(articleId: string): Promise<any> {
    const response = await apiClient.post(`/api/v2/intelligence/full-analysis/${articleId}`);
    return response.data;
  },

  async getSourceProfiles(params?: {
    limit?: number;
    min_credibility?: number;
    source_type?: string;
  }): Promise<SourceProfile[]> {
    const response = await apiClient.get("/api/v2/sources", { params });
    const payload = response.data;
    if (Array.isArray(payload)) {
      return payload;
    }
    if (Array.isArray(payload?.items)) {
      return payload.items;
    }
    if (Array.isArray(payload?.sources)) {
      return payload.sources;
    }
    if (Array.isArray(payload?.data)) {
      return payload.data;
    }
    return [];
  },

  async getSourceProfile(domain: string): Promise<SourceProfile> {
    const response = await apiClient.get(`/api/v2/sources/${encodeURIComponent(domain)}`);
    return response.data;
  },

  async getSourceProfileByName(name: string): Promise<SourceProfile> {
    const response = await apiClient.get(`/api/v2/sources/by-name/${encodeURIComponent(name)}`);
    return response.data;
  },

  async askArticleQuestion(articleId: string, question: string, scope: string = "article"): Promise<ConversationEntry> {
    const response = await apiClient.post(`/api/articles/${articleId}/ask`, { question, scope });
    return response.data;
  },

  async getArticleConversations(articleId: string, limit: number = 10): Promise<ConversationHistory> {
    const response = await apiClient.get(`/api/articles/${articleId}/conversations`, { params: { limit } });
    return response.data;
  },

  async getSimilarArticles(articleId: string, limit: number = 5): Promise<SimilarArticle[]> {
    const response = await apiClient.get(`/api/articles/${articleId}/similar`, { params: { limit } });
    return response.data;
  },

  async getForecasts(countryCode: string): Promise<ForecastComparison> {
    const response = await apiClient.get(`/api/forecasts/${countryCode}`);
    return response.data;
  },

  // Source registration (premium feature)
  async registerSource(payload: {
    source_name: string;
    source_url: string;
    feed_type?: string;
    country_code?: string;
  }): Promise<any> {
    const response = await apiClient.post("/api/sources/register", payload);
    return response.data;
  },

  async getMySources(): Promise<any[]> {
    const response = await apiClient.get("/api/sources/my-sources");
    return response.data;
  },

  async getBookmarkStatus(articleId: string): Promise<{
    article_id: string;
    bookmarked: boolean;
    folder?: string;
    notes?: string | null;
    bookmarked_at?: string;
  }> {
    const response = await apiClient.get(`/api/user/bookmarks/${articleId}/status`);
    return response.data;
  },

  async createBookmark(
    articleId: string,
    payload: { folder?: string; notes?: string } = {},
  ): Promise<{ message: string; article_id: string }> {
    const response = await apiClient.post(`/api/user/bookmarks/${articleId}`, payload);
    return response.data;
  },

  async deleteBookmark(articleId: string): Promise<{ message: string }> {
    const response = await apiClient.delete(`/api/user/bookmarks/${articleId}`);
    return response.data;
  },

  async toggleSource(registrationId: string, isActive: boolean): Promise<any> {
    const response = await apiClient.put(`/api/sources/${registrationId}`, { is_active: isActive });
    return response.data;
  },

  async deleteSource(registrationId: string): Promise<void> {
    await apiClient.delete(`/api/sources/${registrationId}`);
  },

  async validateSourceUrl(url: string): Promise<{ url: string; valid: boolean; title?: string; item_count: number; error?: string }> {
    const response = await apiClient.get("/api/sources/validate", { params: { url } });
    return response.data;
  },

  // Document ingestion (research reports)
  async submitDocument(payload: {
    url?: string;
    content_type?: string;
    doi?: string;
  }): Promise<any> {
    const response = await apiClient.post("/api/ingest/document", payload);
    return response.data;
  },

  // Deep search (Professional+ only)
  async deepSearch(params: {
    query: string;
    country?: string;
    category?: string;
    include_weather?: boolean;
    limit?: number;
  }): Promise<DeepSearchResult> {
    const response = await apiClient.post("/api/deep-search/", params);
    return response.data;
  },

  // Comparative analysis (Professional+ only)
  async compareTopics(params: {
    query_a: string;
    query_b: string;
    country?: string;
  }): Promise<CompareResult> {
    const response = await apiClient.post("/api/deep-search/compare", params, { timeout: 120000 });
    return response.data;
  },

  // Weather context for article (Standard+ only)
  async getArticleWeatherContext(articleId: string): Promise<ArticleWeatherContext> {
    const response = await apiClient.get(`/api/deep-search/weather-context/${articleId}`);
    return response.data;
  },

  // Weather context for specific location (all users)
  async getLocationWeather(
    lat: number,
    lon: number,
    name?: string,
  ): Promise<LocationWeatherContext> {
    const response = await apiClient.get("/api/deep-search/weather-location", {
      params: { lat, lon, name },
    });
    return response.data;
  },
  // Translation endpoints
  async getArticleTranslations(articleId: string): Promise<
    Array<{
      language: string;
      title: string;
      summary: string;
      confidence: number;
      translated_at: string;
    }>
  > {
    const response = await apiClient.get(`/api/articles/${articleId}/translations`);
    return response.data;
  },

  async requestTranslation(articleId: string, targetLang: string): Promise<{ status: string; task_id: string }> {
    const response = await apiClient.post(`/api/articles/${articleId}/translate`, null, {
      params: { target_lang: targetLang },
    });
    return response.data;
  },
  // Analytics endpoints
  async getAnalyticsDashboard(): Promise<AnalyticsDashboard> {
    const response = await apiClient.get("/api/analytics/dashboard");
    return response.data;
  },

  async getAnalyticsTrends(days: number = 30): Promise<ArticleTrend[]> {
    const response = await apiClient.get("/api/analytics/trends", { params: { days } });
    return response.data;
  },

  async getSourcePerformance(
    limit: number = 20,
    sort_by: string = "total_articles",
  ): Promise<SourcePerformance[]> {
    const response = await apiClient.get("/api/analytics/sources", {
      params: { limit, sort_by },
    });
    return response.data;
  },

  async getPipelineStatus(): Promise<PipelineStatus> {
    const response = await apiClient.get("/api/analytics/pipeline");
    return response.data;
  },

  // POST + blob — backend routes are POST-only and JWT-gated; the original
  // <a href="...?format=pdf"> wiring never worked. apiClient already attaches
  // the Authorization header from localStorage; caller handles download.
  async exportArticlePdf(articleId: string): Promise<Blob> {
    const response = await apiClient.post(
      `/api/export/article/${articleId}/pdf`,
      null,
      { responseType: "blob" }
    );
    return response.data as Blob;
  },

  async exportArticleCsv(articleId: string): Promise<Blob> {
    const response = await apiClient.post(
      `/api/export/article/${articleId}/csv`,
      null,
      { responseType: "blob" }
    );
    return response.data as Blob;
  },
};

export default api;
