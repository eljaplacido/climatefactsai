import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Link as LinkIcon, CheckCircle, XCircle, AlertTriangle, Loader } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5200';

interface Analysis {
  id: string;
  url: string;
  status: string;
  progress: number;
  credibility_level?: string;
  claims_found?: number;
  created_at: string;
}

export const URLAnalyzerPage: React.FC = () => {
  const { hasTier } = useAuth();
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [analyses, setAnalyses] = useState<Analysis[]>([]);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/analyze-url`);
      setAnalyses(response.data);
    } catch (error) {
      console.error('Failed to fetch history:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await axios.post(`${API_URL}/api/analyze-url`, {
        url,
        priority: 'normal',
      });
      setUrl('');
      fetchHistory();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit URL');
    } finally {
      setLoading(false);
    }
  };

  if (!hasTier('basic')) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md text-center">
          <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="w-8 h-8 text-yellow-600" />
          </div>
          <h2 className="text-2xl font-bold mb-4">Premium Feature</h2>
          <p className="text-gray-600 mb-6">
            URL analysis is available for Basic, Professional, and Enterprise users.
          </p>
          <a
            href="/pricing"
            className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700"
          >
            View Pricing
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-3xl font-bold mb-8">URL Analyzer</h1>

        {/* Submit Form */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <form onSubmit={handleSubmit}>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Enter URL to Analyze
            </label>
            <div className="flex gap-4">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              />
              <button
                type="submit"
                disabled={loading}
                className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Analyzing...' : 'Analyze'}
              </button>
            </div>
            {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
          </form>
        </div>

        {/* Analysis History */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold">Analysis History</h2>
          </div>
          <div className="divide-y">
            {analyses.length === 0 ? (
              <p className="p-6 text-gray-600 text-center">No analyses yet</p>
            ) : (
              analyses.map((analysis) => (
                <div key={analysis.id} className="p-6 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <LinkIcon className="w-5 h-5 text-gray-400" />
                        <a
                          href={analysis.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline truncate"
                        >
                          {analysis.url}
                        </a>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-600">
                        <span>{new Date(analysis.created_at).toLocaleDateString()}</span>
                        {analysis.status === 'completed' && (
                          <span className="flex items-center gap-1">
                            <CheckCircle className="w-4 h-4 text-green-600" />
                            {analysis.credibility_level}
                          </span>
                        )}
                      </div>
                    </div>
                    <div>
                      {analysis.status === 'pending' && (
                        <span className="flex items-center gap-2 text-gray-600">
                          <Loader className="w-4 h-4 animate-spin" />
                          Pending
                        </span>
                      )}
                      {analysis.status === 'processing' && (
                        <span className="flex items-center gap-2 text-blue-600">
                          <Loader className="w-4 h-4 animate-spin" />
                          {analysis.progress}%
                        </span>
                      )}
                      {analysis.status === 'completed' && (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      )}
                      {analysis.status === 'failed' && (
                        <XCircle className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
