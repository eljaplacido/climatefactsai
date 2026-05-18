// /terms — renders docs/compliance/TERMS_OF_SERVICE.md via the GitHub raw URL,
// so the source of truth stays the markdown file in this repo.
//
// Linked from the signup form's ToS consent checkbox (was 404 before this).

"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

const SOURCE_URL =
  "https://raw.githubusercontent.com/eljasuhonen/climatenews/main/docs/compliance/TERMS_OF_SERVICE.md";

export default function TermsPage() {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(SOURCE_URL)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(setMarkdown)
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold mb-6">Terms of Service</h1>
      {err && (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-red-800">
          Failed to load the terms ({err}). View the source at{" "}
          <a href={SOURCE_URL} className="underline">GitHub</a>.
        </div>
      )}
      {!markdown && !err && <p className="text-gray-500">Loading…</p>}
      {markdown && (
        <article className="prose prose-slate max-w-none">
          <ReactMarkdown>{markdown}</ReactMarkdown>
        </article>
      )}
    </main>
  );
}
