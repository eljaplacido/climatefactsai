"use client";

import { Fingerprint, ExternalLink } from "lucide-react";

export interface AIProvenancePayload {
  model: string;
  prompt_name?: string;
  prompt_version?: string;
  retrieval_strategy?: string;
  timestamp: string;
  methodology_version?: string;
}

interface AIProvenanceBadgeProps {
  provenance: AIProvenancePayload;
  variant?: "inline" | "block";
}

export function buildAiJsonLd(provenance: AIProvenancePayload): Record<string, any> {
  return {
    "@context": "https://schema.org",
    "@type": "ClaimReview",
    "claimReviewed": "AI-generated synthesis",
    "author": {
      "@type": "Organization",
      "name": "Climatefacts.ai",
      "url": "https://climatefacts.ai/methodology",
    },
    "datePublished": provenance.timestamp,
    "itemReviewed": {
      "@type": "SoftwareApplication",
      "name": provenance.model,
      "applicationCategory": "AIApplication",
      "softwareVersion": provenance.prompt_version || undefined,
    },
    "reviewBody": provenance.retrieval_strategy || "",
    sdPublisher: {
      "@type": "Organization",
      name: "Climatefacts.ai",
      url: `https://climatefacts.ai/methodology?v=${provenance.methodology_version || ""}`,
    },
  };
}

export default function AIProvenanceBadge({
  provenance,
  variant = "inline",
}: AIProvenanceBadgeProps) {
  const { model, prompt_name, prompt_version, timestamp, methodology_version } = provenance;

  const shortModel = model?.replace(/-\d{4}-\d{2}-\d{2}/, "") ?? "AI";
  const displayVersion = methodology_version || prompt_version || "";

  return (
    <div
      data-ai-generated="true"
      className={
        variant === "block"
          ? "bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800 rounded-lg p-3 text-xs space-y-1"
          : "inline-flex items-center gap-1.5 text-xs bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-full px-2.5 py-0.5"
      }
      aria-label={`AI-generated using ${shortModel}${displayVersion ? ` version ${displayVersion}` : ""}`}
    >
      <Fingerprint className="w-3 h-3 flex-shrink-0" />
      <span>
        AI-produced · {shortModel}
        {displayVersion && <span className="opacity-75"> · v{displayVersion}</span>}
      </span>
      {variant === "block" && (
        <>
          {prompt_name && (
            <div className="text-teal-600 dark:text-teal-400">
              Prompt: <code className="font-mono">{prompt_name}</code>
              {prompt_version && ` v${prompt_version}`}
            </div>
          )}
          {provenance.retrieval_strategy && (
            <div className="text-teal-600 dark:text-teal-400">
              Retrieval: {provenance.retrieval_strategy}
            </div>
          )}
          <div className="text-teal-600 dark:text-teal-400">
            Generated: {new Date(timestamp).toLocaleString()}
          </div>
          <a
            href="/methodology"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-teal-600 dark:text-teal-400 hover:underline mt-1"
          >
            <ExternalLink className="w-3 h-3" />
            Reproduce via methodology
          </a>
        </>
      )}
    </div>
  );
}
