"use client";

import { useState, useEffect, useMemo } from "react";
import { Loader2, GitBranch, CheckCircle2, XCircle, MinusCircle, ChevronRight } from "lucide-react";
import type { KnowledgeEntity, EntityRelationship, ArticleEntityGraph } from "../types";

interface ArgumentationGraphProps {
  articleId: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const ENTITY_TYPE_COLORS: Record<string, string> = {
  PERSON: "bg-blue-100 text-blue-800 border-blue-300",
  ORGANIZATION: "bg-purple-100 text-purple-800 border-purple-300",
  LOCATION: "bg-green-100 text-green-800 border-green-300",
  POLICY: "bg-amber-100 text-amber-800 border-amber-300",
  EVENT: "bg-red-100 text-red-800 border-red-300",
  TECHNOLOGY: "bg-cyan-100 text-cyan-800 border-cyan-300",
  EMISSION_SOURCE: "bg-orange-100 text-orange-800 border-orange-300",
  CONCEPT: "bg-gray-100 text-gray-800 border-gray-300",
};

const RELATIONSHIP_LABELS: Record<string, { label: string; color: string }> = {
  CAUSES: { label: "causes", color: "text-red-600" },
  AFFECTS: { label: "affects", color: "text-amber-600" },
  REGULATES: { label: "regulates", color: "text-blue-600" },
  FUNDS: { label: "funds", color: "text-green-600" },
  OPPOSES: { label: "opposes", color: "text-red-500" },
  MITIGATES: { label: "mitigates", color: "text-emerald-600" },
  REPORTS_ON: { label: "reports on", color: "text-gray-600" },
  LOCATED_IN: { label: "located in", color: "text-teal-600" },
  MEMBER_OF: { label: "member of", color: "text-purple-600" },
};

export default function ArgumentationGraph({ articleId }: ArgumentationGraphProps) {
  const [data, setData] = useState<ArticleEntityGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [expandedConnections, setExpandedConnections] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const timeout = setTimeout(() => {
      if (!cancelled && loading) setLoading(false);
    }, 15000);

    async function fetchGraph() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/carf/entity-graph/${articleId}`);
        if (!res.ok) throw new Error("Failed to load entity graph");
        const json = await res.json();
        if (!cancelled) {
          setData(json);
          setLoading(false);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      }
    }
    fetchGraph();
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [articleId]);

  const filteredRelationships = useMemo(() => {
    if (!data?.relationships || !selectedEntity) return data?.relationships || [];
    return data.relationships.filter(
      (r) => r.source.entity_id === selectedEntity || r.target.entity_id === selectedEntity
    );
  }, [data, selectedEntity]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-teal-600" />
        <span className="ml-2 text-sm text-gray-500">Loading knowledge graph...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-6 text-sm text-gray-400">
        Knowledge graph not available for this article yet.
      </div>
    );
  }

  if (data.entities.length === 0) {
    return (
      <div className="text-center py-6 text-sm text-gray-400">
        No entities extracted for this article yet.
      </div>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <GitBranch className="h-5 w-5 text-teal-600" />
        <h2 className="text-lg font-semibold text-gray-900">Knowledge Graph</h2>
        <span className="text-xs text-gray-400">
          {data.entities.length} entities, {data.relationships.length} relationships
        </span>
      </div>

      {/* Entity nodes */}
      <div className="flex flex-wrap gap-2">
        {data.entities.map((entity) => (
          <button
            key={entity.entity_id}
            onClick={() =>
              setSelectedEntity(
                selectedEntity === entity.entity_id ? null : entity.entity_id
              )
            }
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
              ENTITY_TYPE_COLORS[entity.entity_type] || ENTITY_TYPE_COLORS.CONCEPT
            } ${
              selectedEntity === entity.entity_id
                ? "ring-2 ring-teal-500 ring-offset-1 scale-105"
                : "hover:scale-105"
            }`}
          >
            <span>{entity.entity_name}</span>
            <span className="text-[10px] opacity-60">{entity.entity_type.toLowerCase()}</span>
          </button>
        ))}
      </div>

      {/* Relationships */}
      {filteredRelationships.length > 0 && (
        <div className="space-y-2 bg-gray-50 rounded-lg p-4 border border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            {selectedEntity ? "Filtered Relationships" : "All Relationships"}
          </h3>
          {filteredRelationships.slice(0, expandedConnections ? undefined : 8).map((rel, i) => {
            const relInfo = RELATIONSHIP_LABELS[rel.relationship_type] || {
              label: rel.relationship_type.toLowerCase().replace(/_/g, " "),
              color: "text-gray-600",
            };
            return (
              <div
                key={i}
                className="flex items-center gap-2 text-sm bg-white rounded-lg px-3 py-2 border border-gray-100"
              >
                <span className="font-medium text-gray-900 truncate max-w-[140px]">
                  {rel.source.entity_name}
                </span>
                <ChevronRight className={`h-4 w-4 flex-shrink-0 ${relInfo.color}`} />
                <span className={`text-xs font-medium ${relInfo.color} flex-shrink-0`}>
                  {relInfo.label}
                </span>
                <ChevronRight className={`h-4 w-4 flex-shrink-0 ${relInfo.color}`} />
                <span className="font-medium text-gray-900 truncate max-w-[140px]">
                  {rel.target.entity_name}
                </span>
                {rel.strength > 0.7 && (
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                )}
                {rel.strength < 0.3 && (
                  <MinusCircle className="h-3 w-3 text-gray-400 flex-shrink-0" />
                )}
              </div>
            );
          })}
          {filteredRelationships.length > 8 && (
            <button
              onClick={() => setExpandedConnections(!expandedConnections)}
              className="text-xs text-teal-600 hover:underline mt-1"
            >
              {expandedConnections
                ? "Show less"
                : `Show all ${filteredRelationships.length} relationships`}
            </button>
          )}
        </div>
      )}

      {/* Connected articles */}
      {data.connected_articles && data.connected_articles.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700">Connected Articles</h3>
          <div className="space-y-1">
            {data.connected_articles.slice(0, 5).map((article) => (
              <a
                key={article.article_id}
                href={`/articles/${article.article_id}`}
                className="block text-sm text-teal-600 hover:underline truncate"
              >
                {article.title}
                <span className="text-xs text-gray-400 ml-2">{article.connection_path}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
