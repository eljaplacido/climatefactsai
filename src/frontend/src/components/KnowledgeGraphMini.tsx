"use client";

// Knowledge Graph mini-view on the article-detail page.
//
// Backend: GET /api/carf/entity-graph/{article_id} returns the entity
// list, relationships, and articles connected via shared entities. The
// data is populated by the GX10 Lane A entity-extraction worker
// (clilens-lane-a-entity systemd service) which runs after the main
// enrichment worker.
//
// Stage 2 (M1) of the Golden Artifact roadmap — exposes the semantic
// layer the user has been asking for: "see how phenomena are connected
// to bigger climate trends, news, releases in the same area, etc."
//
// First-pass implementation is cards + lists rather than a force graph.
// Once the data shapes are validated in production the viz can be
// upgraded to react-flow / d3-force, but the goal here is to surface
// the semantic connections immediately, not to ship pretty visuals.

import { useEffect, useState } from "react";
import Link from "next/link";
import AskAboutButton from "./AskAboutButton";
import {
  Network,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Sparkles,
  AlertCircle,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Entity {
  entity_id: string;
  name: string;
  type: string;
  description: string;
  article_count: number;
  mention_count: number;
  salience: number;
}

interface Relationship {
  relationship_id: string;
  source_entity: string;
  target_entity: string;
  relationship_type: string;
  strength: number;
  confidence: number;
  evidence_text: string;
}

interface ConnectedArticle {
  article_id: string;
  title: string;
  source_name: string;
  credibility: string;
}

interface EntityGraphResponse {
  article_id: string;
  entities: Entity[];
  relationships?: Relationship[];
  connected_articles?: ConnectedArticle[];
  status?: string;
  reason?: string;
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
  DEFAULT: "bg-gray-100 text-gray-800 border-gray-200",
};

function typeStyle(type: string): string {
  return TYPE_COLOR[type?.toUpperCase()] || TYPE_COLOR.DEFAULT;
}

// Solid fills for the SVG relationship graph (the TYPE_COLOR pills are
// tailwind class strings; SVG needs concrete colours).
const TYPE_FILL: Record<string, string> = {
  PERSON: "#9333ea",
  ORGANIZATION: "#2563eb",
  ORG: "#2563eb",
  LOCATION: "#059669",
  GPE: "#059669",
  EVENT: "#d97706",
  POLICY: "#e11d48",
  TECHNOLOGY: "#0891b2",
  CONCEPT: "#475569",
  DEFAULT: "#6b7280",
};

function typeFill(type?: string): string {
  return TYPE_FILL[(type || "").toUpperCase()] || TYPE_FILL.DEFAULT;
}

// "REPORTS_ON" -> "reports on" — the ASCII `━REPORTS_ON━▶` rows the user
// flagged as unintuitive become readable labels.
function humanizeRel(t?: string): string {
  const s = (t || "").replace(/_/g, " ").trim().toLowerCase();
  return s || "related to";
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/**
 * Deterministic circular node-link graph for entity relationships (F7).
 * Fixed geometry (nodes evenly on a circle) so layout is stable and
 * predictable — no force simulation. Nodes coloured by entity type;
 * directed edges carry a humanised relationship label.
 */
function RelationshipGraph({
  relationships,
  entityTypes,
}: {
  relationships: Relationship[];
  entityTypes: Record<string, string>;
}) {
  const names: string[] = [];
  relationships.forEach((r) => {
    if (r.source_entity && !names.includes(r.source_entity)) names.push(r.source_entity);
    if (r.target_entity && !names.includes(r.target_entity)) names.push(r.target_entity);
  });
  const nodes = names.slice(0, 12);
  if (nodes.length < 2) return null;

  const W = 480;
  const H = 340;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(cx, cy) - 95;
  const pos: Record<string, { x: number; y: number; a: number }> = {};
  nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    pos[n] = { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a), a };
  });
  const edges = relationships.filter(
    (r) => pos[r.source_entity] && pos[r.target_entity]
  );

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-auto"
      style={{ overflow: "visible" }}
      role="img"
      aria-label={`Relationship graph: ${nodes.length} entities, ${edges.length} connections`}
    >
      <defs>
        <marker
          id="kg-arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
        </marker>
      </defs>

      {edges.map((r, i) => {
        const s = pos[r.source_entity];
        const t = pos[r.target_entity];
        const mx = (s.x + t.x) / 2;
        const my = (s.y + t.y) / 2;
        return (
          <g key={r.relationship_id || `${r.source_entity}-${r.target_entity}-${i}`}>
            <line
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke="#cbd5e1"
              strokeWidth={1.5}
              markerEnd="url(#kg-arrow)"
            />
            <text
              x={mx}
              y={my}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="9"
              fill="#4338ca"
              style={{ paintOrder: "stroke", stroke: "white", strokeWidth: 3 }}
            >
              {truncate(humanizeRel(r.relationship_type), 22)}
            </text>
          </g>
        );
      })}

      {nodes.map((n) => {
        const p = pos[n];
        const right = Math.cos(p.a) >= -0.2;
        const onAxis = Math.abs(Math.cos(p.a)) < 0.2;
        return (
          <g key={n}>
            <circle
              cx={p.x}
              cy={p.y}
              r={6}
              fill={typeFill(entityTypes[n])}
              stroke="white"
              strokeWidth={1.5}
            />
            <text
              x={p.x + (onAxis ? 0 : right ? 10 : -10)}
              y={p.y + (onAxis ? (Math.sin(p.a) >= 0 ? 16 : -12) : 0)}
              textAnchor={onAxis ? "middle" : right ? "start" : "end"}
              dominantBaseline="middle"
              fontSize="10.5"
              fill="#1e293b"
              style={{ paintOrder: "stroke", stroke: "white", strokeWidth: 3 }}
            >
              {truncate(n, 16)}
            </text>
            <title>{n}</title>
          </g>
        );
      })}
    </svg>
  );
}

interface Props {
  articleId: string;
}

export default function KnowledgeGraphMini({ articleId }: Props) {
  const [data, setData] = useState<EntityGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/carf/entity-graph/${encodeURIComponent(articleId)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: EntityGraphResponse) => {
        if (cancelled) return;
        setData(d);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(String(e?.message || e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [articleId]);

  if (loading) {
    return (
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-3">
          <Network className="h-5 w-5 text-clilens-primary" />
          <h2 className="text-lg font-semibold text-gray-900">Knowledge Graph</h2>
        </div>
        <p className="text-sm text-gray-500">Loading semantic connections…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-3">
          <AlertCircle className="h-5 w-5 text-amber-600" />
          <h2 className="text-lg font-semibold text-gray-900">Knowledge Graph</h2>
        </div>
        <p className="text-sm text-amber-700">Couldn't load entity graph: {error}</p>
      </section>
    );
  }

  if (!data || data.status === "kg_not_populated" || data.entities.length === 0) {
    return (
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-3">
          <Network className="h-5 w-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-900">Knowledge Graph</h2>
        </div>
        <p className="text-sm text-gray-600">
          No entities extracted for this article yet. The GX10 entity-extraction
          worker (clilens-lane-a-entity) processes articles asynchronously after
          enrichment completes — check back after the worker has caught up.
        </p>
        {data?.reason && (
          <p className="text-xs text-gray-400 mt-2 italic">{data.reason}</p>
        )}
        <div className="mt-3">
          <AskAboutButton
            prompt="Why is this article missing from the knowledge graph, and when will the entity-extraction worker process it?"
            variant="chip"
          />
        </div>
      </section>
    );
  }

  const entities = data.entities.slice(0, 15);
  const relationships = (data.relationships || []).slice(0, 10);
  const connected = (data.connected_articles || []).slice(0, 8);
  // name -> type, so the graph can colour each node by its entity type.
  const entityTypes: Record<string, string> = {};
  (data.entities || []).forEach((e) => {
    if (e.name) entityTypes[e.name] = e.type;
  });
  // The graph needs ≥2 distinct entities to be meaningful.
  const relGraphNodes = new Set<string>();
  relationships.forEach((r) => {
    if (r.source_entity) relGraphNodes.add(r.source_entity);
    if (r.target_entity) relGraphNodes.add(r.target_entity);
  });
  const showRelGraph = relGraphNodes.size >= 2;

  return (
    <section className="bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between p-6 hover:bg-white/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center">
            <Network className="h-5 w-5 text-white" />
          </div>
          <div className="text-left">
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-1">
              Knowledge Graph
              <AskAboutButton
                prompt="Explain what the knowledge graph shows for this article and why these entities are connected"
                ariaLabel="Ask the assistant: explain this knowledge graph"
              />
            </h2>
            <p className="text-sm text-gray-600">
              {entities.length} entities · {relationships.length} relationships · {connected.length} connected articles
            </p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-5 w-5 text-gray-500" />
        ) : (
          <ChevronDown className="h-5 w-5 text-gray-500" />
        )}
      </button>

      {expanded && (
        <div className="px-6 pb-6 space-y-5">
          {/* Entities — click any pill to drill into its full
              neighborhood + cross-article connections via M5
              /explore/entity/{id} page. */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">
              Entities mentioned
            </h3>
            <div className="flex flex-wrap gap-2">
              {entities.map((e) => (
                <Link
                  key={e.entity_id}
                  href={`/explore/entity/${e.entity_id}`}
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border transition-shadow hover:shadow-sm ${typeStyle(e.type)}`}
                  title={`${e.description || e.type} — click to explore connections`}
                >
                  <span>{e.name}</span>
                  <span className="opacity-60">·{e.type}</span>
                  {e.article_count > 1 && (
                    <span className="ml-1 px-1 bg-white/50 rounded">
                      in {e.article_count}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          </div>

          {/* Relationships — visual node-link graph (F7). The previous
              ASCII `━REPORTS_ON━▶` rows are kept as a collapsible "List
              view" below for precision + screen-reader access. */}
          {relationships.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                Relationships
              </h3>
              {showRelGraph && (
                <div className="bg-white/60 rounded-lg border border-white/80 p-3">
                  <RelationshipGraph
                    relationships={relationships}
                    entityTypes={entityTypes}
                  />
                </div>
              )}
              <details className="mt-2 group">
                <summary className="text-xs text-indigo-700 cursor-pointer select-none hover:underline">
                  List view ({relationships.length})
                </summary>
                <ul className="space-y-1.5 mt-2">
                  {relationships.map((r, i) => (
                    <li
                      key={r.relationship_id || `${r.source_entity}-${i}`}
                      className="text-sm bg-white/60 rounded-md px-3 py-1.5 border border-white/80"
                    >
                      <span className="font-medium text-gray-900">{r.source_entity}</span>
                      <span className="mx-2 text-xs text-indigo-700 lowercase">
                        {humanizeRel(r.relationship_type)} →
                      </span>
                      <span className="font-medium text-gray-900">{r.target_entity}</span>
                      {r.confidence > 0 && (
                        <span className="ml-2 text-xs text-gray-500">
                          ({Math.round(r.confidence * 100)}% conf)
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          )}

          {/* Connected articles via shared entities */}
          {connected.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1">
                <Sparkles className="h-4 w-4 text-indigo-600" />
                Related coverage (via shared entities)
              </h3>
              <ul className="space-y-1.5">
                {connected.map((c) => (
                  <li key={c.article_id}>
                    <Link
                      href={`/articles/${c.article_id}`}
                      className="block bg-white/80 hover:bg-white border border-white rounded-md px-3 py-2 text-sm transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-gray-900 line-clamp-1 flex-1">
                          {c.title}
                        </span>
                        <ExternalLink className="h-3.5 w-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {c.source_name}
                        {c.credibility && c.credibility !== "UNKNOWN" && (
                          <span className="ml-2 uppercase tracking-wide">
                            · {c.credibility}
                          </span>
                        )}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
