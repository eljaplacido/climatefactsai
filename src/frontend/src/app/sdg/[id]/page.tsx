"use client";

// Stage 6 / M7 — SDG cross-artifact browse page.
//
// Loads /api/sdg/{goal_id} which scans articles + companies for any
// keyword match against the goal's keyword set. Each artifact links
// back into the rest of the platform (article detail, company detail).

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Loader2, ExternalLink, Building2, Newspaper } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Goal {
  id: number;
  title: string;
  color: string;
  icon: string;
}
interface ArticleRef {
  article_id: string;
  title: string;
  source_name: string;
  country_code: string;
  credibility: string;
  published_date: string | null;
}
interface CompanyRef {
  company_id: string;
  name: string;
  ticker: string | null;
  country_code: string | null;
  sector: string | null;
}
interface SDGResponse {
  goal: Goal;
  articles: ArticleRef[];
  companies: CompanyRef[];
  article_count: number;
  company_count: number;
}

export default function SDGPage() {
  const params = useParams();
  const goalId = Number(params?.id);
  const [data, setData] = useState<SDGResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!goalId || goalId < 1 || goalId > 17) {
      setError("Invalid SDG goal id (must be 1-17)");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/api/sdg/${goalId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: SDGResponse) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e?.message || e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [goalId]);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <Loader2 className="h-5 w-5 animate-spin text-clilens-primary inline mr-2" />
        Loading SDG {goalId}…
      </div>
    );
  }
  if (error) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <p className="text-rose-700">{error}</p>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <Link href="/" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900">
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back
      </Link>

      <header
        className="rounded-xl p-6 text-white"
        style={{ backgroundColor: data.goal.color }}
      >
        <div className="flex items-start gap-4">
          <div className="text-6xl">{data.goal.icon}</div>
          <div>
            <p className="text-sm opacity-90">UN Sustainable Development Goal {data.goal.id}</p>
            <h1 className="text-3xl font-bold mt-1">{data.goal.title}</h1>
            <p className="text-sm opacity-90 mt-2">
              {data.article_count} articles · {data.company_count} companies in the corpus
              match this goal.
            </p>
          </div>
        </div>
      </header>

      {/* Articles */}
      <section className="bg-white border border-gray-200 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide flex items-center gap-2">
          <Newspaper className="h-4 w-4" />
          Articles ({data.article_count})
        </h2>
        {data.articles.length === 0 ? (
          <p className="text-sm text-gray-500">No articles yet tagged to this SDG.</p>
        ) : (
          <ul className="space-y-2">
            {data.articles.map((a) => (
              <li key={a.article_id}>
                <Link
                  href={`/articles/${a.article_id}`}
                  className="block px-3 py-2 hover:bg-gray-50 rounded-md border border-gray-100"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm text-gray-900 font-medium">{a.title}</span>
                    <ExternalLink className="h-3.5 w-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {a.source_name}
                    {a.country_code && ` · ${a.country_code}`}
                    {a.published_date && ` · ${a.published_date.slice(0, 10)}`}
                    {a.credibility && a.credibility !== "UNKNOWN" && ` · ${a.credibility}`}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Companies */}
      {data.companies.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Companies ({data.company_count})
          </h2>
          <ul className="space-y-2">
            {data.companies.map((c) => (
              <li key={c.company_id}>
                <Link
                  href={`/companies/${c.ticker || c.company_id}`}
                  className="block px-3 py-2 hover:bg-gray-50 rounded-md border border-gray-100"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="text-sm text-gray-900 font-medium">{c.name}</span>
                      {c.ticker && (
                        <span className="ml-2 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                          {c.ticker}
                        </span>
                      )}
                    </div>
                    <ExternalLink className="h-3.5 w-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {c.country_code && `${c.country_code}`}
                    {c.sector && ` · ${c.sector}`}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
