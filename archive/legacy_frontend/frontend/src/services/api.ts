/**
 * API Client - Climate News Backend
 */

import axios from 'axios';
import type { Article, ArticleDetail, DashboardStats, WorkflowStatus, TagStat, FeedbackSummary, FeedbackRequestPayload } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5200';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  /**
   * Fetch articles
   */

async getArticles(params?: {
  limit?: number;
  offset?: number;
  date_from?: string;
  date_to?: string;
  credibility?: 'HIGH' | 'MEDIUM' | 'LOW';
  country?: string;
  source?: string;
  tags?: string[];
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
  };

  const response = await apiClient.get('/api/articles', {
    params: query,
    paramsSerializer: (queryParams) => {
      const searchParams = new URLSearchParams();
      Object.entries(queryParams).forEach(([key, value]) => {
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

  /**
   * Fetch countries
   */
  async getCountries(): Promise<any[]> {
    const response = await apiClient.get('/api/countries');
    return response.data;
  },

  /**
   * Fetch a single article
   */
  async getArticleDetail(articleId: string): Promise<ArticleDetail> {
    const response = await apiClient.get(`/api/articles/${articleId}`);
    return response.data;
  },

  /**
   * Fetch dashboard statistics
   */
  async getStats(): Promise<DashboardStats> {
    const response = await apiClient.get('/api/stats');
    return response.data;
  },

  /**
   * Admin: Fetch dashboard statistics
   */
  async getAdminDashboard(): Promise<DashboardStats> {
    const response = await apiClient.get('/api/admin/dashboard');
    return response.data;
  },

  /**
   * Admin: Trigger workflow
   */
  async triggerWorkflow(taskId?: string): Promise<{ task_id: string; status: string; message: string }> {
    const response = await apiClient.post('/api/admin/trigger-workflow', { task_id: taskId });
    return response.data;
  },

  /**
   * Admin: Fetch workflow history
   */
  async getWorkflows(limit: number = 10): Promise<WorkflowStatus[]> {
    const response = await apiClient.get('/api/admin/workflows', { params: { limit } });
    return response.data;
  },

/**
 * Fetch top tags
 */
async getTagStats(country?: string): Promise<TagStat[]> {
  const response = await apiClient.get('/api/tags', {
    params: { country },
  });
  return response.data;
},

/**
 * Submit article feedback
 */
async submitFeedback(articleId: string, payload: FeedbackRequestPayload) {
  const response = await apiClient.post(`/api/articles/${articleId}/feedback`, payload);
  return response.data;
},

/**
 * Fetch article feedback summary
 */
async getFeedbackSummary(articleId: string): Promise<FeedbackSummary> {
  const response = await apiClient.get(`/api/articles/${articleId}/feedback`);
  return response.data;
},

};

export default api;



