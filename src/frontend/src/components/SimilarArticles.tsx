"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles, ExternalLink } from "lucide-react";
import type { SimilarArticle } from "@/types";
import { api } from "@/lib/api";

interface SimilarArticlesProps {
  articleId: string;
}

export default function SimilarArticles({ articleId }: SimilarArticlesProps) {
  const [articles, setArticles] = useState<SimilarArticle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getSimilarArticles(articleId, 5);
        setArticles(data);
      } catch {
        // Non-critical feature
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [articleId]);

  if (loading || articles.length === 0) return null;

  const credColor: Record<string, string> = {
    HIGH: "text-green-600 bg-green-50",
    MEDIUM: "text-yellow-600 bg-yellow-50",
    LOW: "text-red-600 bg-red-50",
  };

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-clilens-primary" />
        Similar Articles
      </h2>
      <div className="grid gap-3">
        {articles.map((a) => (
          <Link
            key={a.article_id}
            href={`/articles/${a.article_id}`}
            className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate group-hover:text-clilens-primary transition-colors">
                {a.title}
              </p>
              <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                <span>{a.source_name}</span>
                {a.published_date && (
                  <>
                    <span>·</span>
                    <span>{new Date(a.published_date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span>
                  </>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 ml-3 flex-shrink-0">
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${credColor[a.overall_credibility] || "text-gray-500 bg-gray-100"}`}>
                {a.overall_credibility}
              </span>
              <span className="text-xs text-gray-400">{Math.round(a.similarity_score * 100)}%</span>
              <ExternalLink className="h-3.5 w-3.5 text-gray-300 group-hover:text-clilens-primary" />
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
