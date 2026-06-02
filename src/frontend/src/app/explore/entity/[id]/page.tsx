"use client";

// Entity drill-down page — Stage 4 / M5.
//
// Reached from the Knowledge Graph mini-view on the article-detail
// page (click any entity pill → land here). Renders the entity's
// neighborhood: connected entities, all articles that mention the
// entity, and a "why connected" LLM-explained synthesis when the
// user picks 2+ articles.
//
// Powered by GET /api/semantic/entity/{entity_id} +
// POST /api/semantic/explain.

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  Network,
  ArrowLeft,
  Sparkles,
  ExternalLink,
  Loader2,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Entity {
  entity_id: string;
  name: string;
  type: string;
  description: string;
  article_count: number;
}
interface Neighbor {
  entity_id: string;
  name: string;
  type: string;
}
interface Relationship {
  relationship_id: string;
  source: { id: string; name: string; type?: string };
  target: { id: string; name: string; type?: string };
  type: string;
  strength: number;
  confidence: number;
  evidence_text: string;
}
interface ArticleRef {
  article_id: string;
  title: string;
  source_name: string;
  country_code: string;
  published_date: string | null;
  credibility: string;
  mention_count: number;
  salience: number;
}
interface EntityProfile {
  entity: Entity;
  neighbors: Neighbor[];
  relationships: Relationship[];
  articles: ArticleRef[];
}

const TYPE_COLOR: Record<string, string> = {
  PERSON: "bg-purple-100 text-purple-800 border-purple-200",
  ORGANIZATION: "bg-blue-100 text-blue-800 border-blue-200",
  ORG: "bg-blue-100 text-blue-800 border-blue-200",
  LOCATION: "bg-emerald-100 text-emerald-800 border-emerald-200",
  GPE: "bg-emerald-100 text-emerald-800 border-emerald-200",
  EVENT: "bg-amber-100 text-amber-800 border-amber-200",
  POLICY: "bg-rose-100 text-rose-800 border-rose-200",
  TECHNOLOGY: "bg-cyan-100 text-cyan-800 border-cyan-200",
  CONCEPT: "bg-slate-100 text-slate-700 border-slate-200",
};

function typeStyle(t: string): string {
  return TYPE_COLOR[(t || "").toUpperCase()] || "bg-gray-100 text-gray-800 border-gray-200";
}

// useSearchParams (below) requires the route to opt out of static prerender
// and the reader to sit under a Suspense boundary (Next.js 14).
export const dynamic = "force-dynamic";

function EntityPageInner() {
  const params = useParams();
  const searchParams = useSearchParams();
  const entityId = String(params?.id || "");
  // When reached from an article's knowledge graph, ?from={articleId} lets the
  // back link return to that article instead of dumping the user on home.
  const fromArticle = searchParams?.get("from");
  const backHref = fromArticle ? `/articles/${fromArticle}` : "/";
  const backLabel = fromArticle ? "Back to article" : "Back home";
  const [data, setData] = useState<EntityProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // "Why connected" state
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [explanation, setExplanation] = useState<{
    explanation: string;
    bridges: any[];
    llm_provider?: string;
  } | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);

  useEffect(() => {
    if (!entityId) return;
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/api/semantic/entity/${encodeURIComponent(entityId)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: EntityProfile) => {
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
  }, [entityId]);

  const togglePick = (id: string) => {
    setExplanation(null);
    setPicked((p) => {
      const next = new Set(p);
      if (next.has(id)) next.delete(id);
      else if (next.size < 5) next.add(id);
      return next;
    });
  };

  const runExplain = async () => {
    if (picked.size < 2) return;
    setExplainLoading(true);
    setExplanation(null);
    try {
      const res = await fetch(`${API_BASE}/api/semantic/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ article_ids: Array.from(picked) }),
      });
      const j = await res.json();
      setExplanation(j);
    } catch (e) {
      console.error("explain failed", e);
    } finally {
      setExplainLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <Loader2 className="h-5 w-5 animate-spin text-clilens-primary inline mr-2" />
        Loading entity…
      </div>
    );
  }
  if (error) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <p className="text-rose-700">Couldn&apos;t load entity: {error}</p>
        <Link href={backHref} className="text-clilens-primary hover:underline mt-3 inline-block">
          ← {backLabel}
        </Link>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <Link
        href={backHref}
        className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        {backLabel}
      </Link>

      <header className="bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200 rounded-xl p-6">
        <div className="flex items-start gap-3">
          <div className="w-12 h-12 bg-indigo-600 rounded-full flex items-center justify-center flex-shrink-0">
            <Network className="h-6 w-6 text-white" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl font-bold text-gray-900">{data.entity.name}</h1>
              <span
                className={`px-2 py-0.5 text-xs font-medium rounded-md border ${typeStyle(data.entity.type)}`}
              >
                {data.entity.type}
              </span>
            </div>
            {data.entity.description && (
              <p className="text-sm text-gray-700 mt-1">{data.entity.description}</p>
            )}
            <p className="text-xs text-gray-500 mt-2">
              Mentioned in {data.entity.article_count} articles
              {data.neighbors.length > 0 && ` · ${data.neighbors.length} connected entities`}
            </p>
          </div>
        </div>
      </header>

      {/* Connected entities */}
      {data.neighbors.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
            Connected entities ({data.neighbors.length})
          </h2>
          <div className="flex flex-wrap gap-2">
            {data.neighbors.map((n) => (
              <Link
                key={n.entity_id}
                href={`/explore/entity/${n.entity_id}`}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border hover:shadow ${typeStyle(n.type)}`}
              >
                <span>{n.name}</span>
                <span className="opacity-60">·{n.type}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Relationships */}
      {data.relationships.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
            Relationships ({data.relationships.length})
          </h2>
          <ul className="space-y-1.5">
            {data.relationships.slice(0, 20).map((r) => (
              <li key={r.relationship_id} className="text-sm bg-gray-50 rounded-md px-3 py-2 border border-gray-100">
                <Link
                  href={`/explore/entity/${r.source.id}`}
                  className="font-medium text-indigo-700 hover:underline"
                >
                  {r.source.name}
                </Link>
                <span className="mx-2 text-xs text-indigo-700 font-mono">━{r.type}━▶</span>
                <Link
                  href={`/explore/entity/${r.target.id}`}
                  className="font-medium text-indigo-700 hover:underline"
                >
                  {r.target.name}
                </Link>
                <span className="ml-2 text-xs text-gray-500">
                  ({Math.round((r.confidence || 0) * 100)}% conf)
                </span>
                {r.evidence_text && (
                  <p className="text-xs text-gray-500 italic mt-1">
                    &ldquo;{r.evidence_text.slice(0, 200)}&rdquo;
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Articles mentioning this entity — selectable for "explain connection" */}
      <section className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Articles mentioning &quot;{data.entity.name}&quot; ({data.articles.length})
          </h2>
          <button
            onClick={runExplain}
            disabled={picked.size < 2 || explainLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {explainLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Explain connection ({picked.size}/5)
          </button>
        </div>

        {explanation && (
          <div className="mb-4 bg-indigo-50 border border-indigo-200 rounded-md p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-indigo-600" />
              <h3 className="text-sm font-semibold text-indigo-900">
                Why these are connected
              </h3>
              {explanation.llm_provider && (
                <span className="ml-auto text-xs text-indigo-600 font-mono">
                  via {explanation.llm_provider}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-800 leading-relaxed">{explanation.explanation}</p>
            {explanation.bridges?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-indigo-200">
                <p className="text-xs font-medium text-indigo-800 mb-1.5">
                  Shared entities ({explanation.bridges.length}):
                </p>
                <div className="flex flex-wrap gap-1">
                  {explanation.bridges.slice(0, 12).map((b: any) => (
                    <span
                      key={b.id}
                      className="px-2 py-0.5 text-xs bg-white border border-indigo-200 rounded text-indigo-700"
                    >
                      {b.name}
                      <span className="ml-1 opacity-50">×{b.shared_count}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <ul className="space-y-2">
          {data.articles.map((a) => (
            <li
              key={a.article_id}
              className={`border rounded-md transition-colors ${
                picked.has(a.article_id)
                  ? "bg-indigo-50 border-indigo-300"
                  : "bg-white border-gray-200 hover:border-gray-300"
              }`}
            >
              <div className="flex items-start gap-3 px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={picked.has(a.article_id)}
                  onChange={() => togglePick(a.article_id)}
                  className="mt-1 h-4 w-4"
                  disabled={!picked.has(a.article_id) && picked.size >= 5}
                />
                <div className="flex-1">
                  <Link
                    href={`/articles/${a.article_id}`}
                    className="text-sm text-gray-900 hover:text-clilens-primary font-medium"
                  >
                    {a.title}
                    <ExternalLink className="inline h-3 w-3 ml-1 text-gray-400" />
                  </Link>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {a.source_name}
                    {a.country_code && ` · ${a.country_code}`}
                    {a.published_date && ` · ${a.published_date.slice(0, 10)}`}
                    {a.credibility && a.credibility !== "UNKNOWN" && ` · ${a.credibility}`}
                    {a.salience > 0 && (
                      <span className="ml-2">
                        salience {(a.salience * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default function EntityPage() {
  return (
    <Suspense fallback={<div className="max-w-5xl mx-auto p-6 text-gray-500">Loading entity…</div>}>
      <EntityPageInner />
    </Suspense>
  );
}
