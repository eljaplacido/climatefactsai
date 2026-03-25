import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import {
  BarChart3,
  FileText,
  Search,
  Link as LinkIcon,
  Key,
  Crown,
  TrendingUp,
  Clock,
  Bell,
  Settings,
} from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5200';

interface DashboardData {
  user: {
    id: string;
    email: string;
    full_name: string;
    tier: string;
  };
  usage: {
    tier: string;
    period: string;
    articles_viewed: number;
    articles_limit: number;
    searches_performed: number;
    searches_limit: number;
    url_analyses: number;
    url_analyses_limit: number;
    api_calls: number;
    api_calls_limit: number;
  };
  notifications: {
    unread_count: number;
  };
  subscription: {
    tier: string;
    status: string;
    expires: string | null;
  };
  saved_searches_count: number;
  url_analyses: {
    total: number;
    completed: number;
    in_progress: number;
  };
}

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/user/dashboard`);
        setDashboardData(response.data);
      } catch (error) {
        console.error('Failed to fetch dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!dashboardData) {
    return <div className="p-8">Failed to load dashboard</div>;
  }

  const { usage, notifications, subscription, saved_searches_count, url_analyses } = dashboardData;

  const getProgressColor = (used: number, limit: number) => {
    if (limit === -1) return 'bg-green-500';
    const percentage = (used / limit) * 100;
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 70) return 'bg-yellow-500';
    return 'bg-blue-500';
  };

  const getProgressPercentage = (used: number, limit: number) => {
    if (limit === -1) return 0;
    return Math.min((used / limit) * 100, 100);
  };

  const tierColors = {
    freemium: 'bg-gray-100 text-gray-800',
    basic: 'bg-blue-100 text-blue-800',
    professional: 'bg-purple-100 text-purple-800',
    enterprise: 'bg-yellow-100 text-yellow-800',
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
              <p className="text-gray-600 mt-1">Welcome back, {user?.full_name}</p>
            </div>
            <div className="flex items-center space-x-4">
              {/* Tier Badge */}
              <span
                className={`px-4 py-2 rounded-full text-sm font-medium flex items-center ${
                  tierColors[subscription.tier as keyof typeof tierColors]
                }`}
              >
                <Crown className="w-4 h-4 mr-2" />
                {subscription.tier.charAt(0).toUpperCase() + subscription.tier.slice(1)}
              </span>

              {/* Notifications */}
              <Link
                to="/notifications"
                className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
              >
                <Bell className="w-6 h-6" />
                {notifications.unread_count > 0 && (
                  <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-red-500"></span>
                )}
              </Link>

              {/* Settings */}
              <Link
                to="/settings"
                className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
              >
                <Settings className="w-6 h-6" />
              </Link>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upgrade Banner (for freemium users) */}
        {subscription.tier === 'freemium' && (
          <div className="mb-6 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold mb-2">Unlock Premium Features</h3>
                <p className="text-blue-100">
                  Upgrade to access URL analysis, semantic search, exports, and more!
                </p>
              </div>
              <Link
                to="/pricing"
                className="bg-white text-blue-600 px-6 py-3 rounded-lg font-medium hover:bg-blue-50 transition"
              >
                View Plans
              </Link>
            </div>
          </div>
        )}

        {/* Usage Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Articles Viewed */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <FileText className="w-6 h-6 text-blue-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">
                {usage.articles_viewed}
                {usage.articles_limit !== -1 && `/${usage.articles_limit}`}
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-600 mb-2">Articles Viewed</h3>
            {usage.articles_limit !== -1 && (
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${getProgressColor(
                    usage.articles_viewed,
                    usage.articles_limit
                  )}`}
                  style={{
                    width: `${getProgressPercentage(usage.articles_viewed, usage.articles_limit)}%`,
                  }}
                ></div>
              </div>
            )}
          </div>

          {/* Searches */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <Search className="w-6 h-6 text-green-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">
                {usage.searches_performed}
                {usage.searches_limit !== -1 && `/${usage.searches_limit}`}
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-600 mb-2">Searches</h3>
            {usage.searches_limit !== -1 && (
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${getProgressColor(
                    usage.searches_performed,
                    usage.searches_limit
                  )}`}
                  style={{
                    width: `${getProgressPercentage(
                      usage.searches_performed,
                      usage.searches_limit
                    )}%`,
                  }}
                ></div>
              </div>
            )}
          </div>

          {/* URL Analyses */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-purple-100 rounded-lg">
                <LinkIcon className="w-6 h-6 text-purple-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">
                {usage.url_analyses}
                {usage.url_analyses_limit !== -1 && `/${usage.url_analyses_limit}`}
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-600 mb-2">URL Analyses</h3>
            {usage.url_analyses_limit !== -1 && usage.url_analyses_limit > 0 ? (
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${getProgressColor(
                    usage.url_analyses,
                    usage.url_analyses_limit
                  )}`}
                  style={{
                    width: `${getProgressPercentage(usage.url_analyses, usage.url_analyses_limit)}%`,
                  }}
                ></div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Upgrade to access</p>
            )}
          </div>

          {/* API Calls */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-orange-100 rounded-lg">
                <Key className="w-6 h-6 text-orange-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">
                {usage.api_calls}
                {usage.api_calls_limit !== -1 && `/${usage.api_calls_limit}`}
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-600 mb-2">API Calls</h3>
            {usage.api_calls_limit !== -1 && usage.api_calls_limit > 0 ? (
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${getProgressColor(usage.api_calls, usage.api_calls_limit)}`}
                  style={{
                    width: `${getProgressPercentage(usage.api_calls, usage.api_calls_limit)}%`,
                  }}
                ></div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Professional+ only</p>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Link
            to="/analyze-url"
            className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-blue-100 rounded-lg group-hover:bg-blue-200 transition">
                <LinkIcon className="w-6 h-6 text-blue-600" />
              </div>
              <TrendingUp className="w-5 h-5 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Analyze URL</h3>
            <p className="text-sm text-gray-600">Submit a URL for fact-checking analysis</p>
            {url_analyses.in_progress > 0 && (
              <div className="mt-3 text-sm text-blue-600 font-medium">
                {url_analyses.in_progress} in progress
              </div>
            )}
          </Link>

          <Link
            to="/saved-searches"
            className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-green-100 rounded-lg group-hover:bg-green-200 transition">
                <Search className="w-6 h-6 text-green-600" />
              </div>
              <span className="text-sm font-medium text-gray-500">{saved_searches_count}</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Saved Searches</h3>
            <p className="text-sm text-gray-600">Manage your saved search queries</p>
          </Link>

          <Link
            to="/api-keys"
            className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-purple-100 rounded-lg group-hover:bg-purple-200 transition">
                <Key className="w-6 h-6 text-purple-600" />
              </div>
              <Clock className="w-5 h-5 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">API Keys</h3>
            <p className="text-sm text-gray-600">Manage programmatic access</p>
          </Link>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">Recent Activity</h2>
          </div>
          <div className="p-6">
            <p className="text-gray-600 text-center py-8">
              Your recent activity will appear here
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
