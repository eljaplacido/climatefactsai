"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import Link from "next/link";

const SOURCE_URL =
  "https://raw.githubusercontent.com/eljaplacido/climatefactsai/main/docs/compliance/DATA_PROCESSING.md";

export default function CookiesPage() {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(SOURCE_URL, { headers: { Accept: "text/plain" } });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const text = await res.text();
        if (!cancelled) setMarkdown(text);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Failed to load");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <Link href="/" className="text-teal-700 hover:underline text-sm mb-6 inline-block">
          ← Back to Climatefacts.ai
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Cookie Policy</h1>
        {err && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            Failed to load the cookie policy: {err}. Please contact contact@cisuregen.com.
          </div>
        )}
        {!markdown && !err && (
          <div className="text-gray-400 text-sm animate-pulse">Loading cookie policy…</div>
        )}
        {markdown && (
          <article className="prose prose-gray max-w-none bg-white rounded-lg border border-gray-200 p-6">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}
