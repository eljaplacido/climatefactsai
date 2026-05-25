"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

type Format = "csv" | "pdf";

interface ArticleExportButtonsProps {
  articleId: string;
}

function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

function messageFor(format: Format, status: number | undefined): string {
  if (status === 401)
    return "Sign in to export. Free, Basic, Professional and Enterprise tiers can sign in to download.";
  if (status === 403)
    return `${format.toUpperCase()} export requires Professional or Enterprise subscription.`;
  if (status === 404) return "Article not found.";
  if (status === 501) return "PDF export is currently unavailable on this server.";
  return `${format.toUpperCase()} export failed. Please try again.`;
}

export default function ArticleExportButtons({ articleId }: ArticleExportButtonsProps) {
  const [busy, setBusy] = useState<Format | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport(format: Format) {
    if (busy) return;
    setBusy(format);
    setError(null);
    try {
      const blob =
        format === "pdf"
          ? await api.exportArticlePdf(articleId)
          : await api.exportArticleCsv(articleId);
      triggerDownload(blob, `clilens_article_${articleId.slice(0, 8)}.${format}`);
    } catch (err: unknown) {
      const status =
        typeof err === "object" && err && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      setError(messageFor(format, status));
    } finally {
      setBusy(null);
    }
  }

  const buttonBase =
    "inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-clilens-primary border border-gray-200 rounded hover:border-clilens-primary transition disabled:opacity-50 disabled:cursor-not-allowed";

  return (
    <div className="inline-flex flex-col gap-1">
      <div className="inline-flex items-center gap-2">
        <button
          type="button"
          onClick={() => handleExport("csv")}
          disabled={busy !== null}
          className={buttonBase}
          aria-label="Export article as CSV"
        >
          {busy === "csv" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Download className="h-3 w-3" />
          )}
          CSV
        </button>
        <button
          type="button"
          onClick={() => handleExport("pdf")}
          disabled={busy !== null}
          className={buttonBase}
          aria-label="Export article as PDF"
        >
          {busy === "pdf" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Download className="h-3 w-3" />
          )}
          PDF
        </button>
      </div>
      {error && (
        <p className="text-[11px] text-amber-600 dark:text-amber-400" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
