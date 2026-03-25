"use client";

import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import type { TagStat } from "@/types";
import { TrendingUp, ChevronLeft, ChevronRight } from "lucide-react";

interface TrendingTopicsProps {
  onTopicClick?: (tag: string) => void;
  activeTag?: string | null;
  country?: string;
}

export default function TrendingTopics({ onTopicClick, activeTag, country }: TrendingTopicsProps) {
  const [tags, setTags] = useState<TagStat[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function fetchTags() {
      try {
        const data = await api.getTagStats(country);
        setTags(data.slice(0, 20));
      } catch {
        setTags([]);
      } finally {
        setLoading(false);
      }
    }
    fetchTags();
  }, [country]);

  function scroll(direction: "left" | "right") {
    if (!scrollRef.current) return;
    const amount = 200;
    scrollRef.current.scrollBy({
      left: direction === "left" ? -amount : amount,
      behavior: "smooth",
    });
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 overflow-hidden py-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-8 w-24 bg-gray-100 rounded-full animate-pulse flex-shrink-0" />
        ))}
      </div>
    );
  }

  if (tags.length === 0) return null;

  return (
    <div className="relative">
      <div className="flex items-center gap-2 mb-2">
        <TrendingUp className="h-4 w-4 text-clilens-primary" />
        <span className="text-sm font-semibold text-gray-700">Trending Topics</span>
      </div>

      <div className="relative group">
        {/* Left scroll button */}
        <button
          onClick={() => scroll("left")}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-8 h-8 bg-white/90 shadow-md rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <ChevronLeft className="h-4 w-4 text-gray-600" />
        </button>

        {/* Scrollable container */}
        <div
          ref={scrollRef}
          className="flex gap-2 overflow-x-auto scrollbar-hide py-1 px-1"
          style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
        >
          {tags.map((tag) => (
            <button
              key={tag.tag}
              onClick={() => onTopicClick?.(tag.tag)}
              className={`flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border transition-all duration-200 hover:shadow-sm ${
                activeTag === tag.tag
                  ? "bg-clilens-primary text-white border-clilens-primary"
                  : "bg-white text-gray-700 border-gray-200 hover:border-clilens-primary hover:text-clilens-primary"
              }`}
            >
              <span>{tag.tag.replace(/_/g, " ")}</span>
              <span className={`text-xs ${activeTag === tag.tag ? "text-white/80" : "text-gray-400"}`}>
                {tag.article_count}
              </span>
            </button>
          ))}
        </div>

        {/* Right scroll button */}
        <button
          onClick={() => scroll("right")}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-8 h-8 bg-white/90 shadow-md rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <ChevronRight className="h-4 w-4 text-gray-600" />
        </button>
      </div>
    </div>
  );
}
