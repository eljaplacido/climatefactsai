"use client";

import { CheckCircle2, XCircle, MinusCircle, ExternalLink } from "lucide-react";
import type { EvidenceChainLink } from "@/types";

interface EvidenceTimelineProps {
  chain: EvidenceChainLink[];
}

export default function EvidenceTimeline({ chain }: EvidenceTimelineProps) {
  if (!chain || chain.length === 0) return null;

  return (
    <div className="space-y-0">
      {chain.map((link, idx) => {
        const isLast = idx === chain.length - 1;
        const StatusIcon =
          link.supports_claim === true
            ? CheckCircle2
            : link.supports_claim === false
            ? XCircle
            : MinusCircle;
        const statusColor =
          link.supports_claim === true
            ? "text-green-500"
            : link.supports_claim === false
            ? "text-red-500"
            : "text-gray-400";
        const lineColor =
          link.supports_claim === true
            ? "bg-green-200"
            : link.supports_claim === false
            ? "bg-red-200"
            : "bg-gray-200";

        return (
          <div key={link.step_number} className="flex gap-3">
            {/* Timeline connector */}
            <div className="flex flex-col items-center">
              <div className={`flex-shrink-0 ${statusColor}`}>
                <StatusIcon className="h-5 w-5" />
              </div>
              {!isLast && <div className={`w-0.5 flex-1 min-h-[24px] ${lineColor}`} />}
            </div>

            {/* Content */}
            <div className={`flex-1 pb-4 ${isLast ? "" : ""}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm text-gray-800">{link.description}</p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    Source: {link.source}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-[10px] font-medium text-gray-400">
                    {Math.round(link.confidence * 100)}%
                  </span>
                  {link.source_url && (
                    <a
                      href={link.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-300 hover:text-clilens-primary transition-colors"
                    >
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>

              {/* Confidence bar */}
              <div className="mt-1.5 flex items-center gap-2">
                <div className="w-20 h-1 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-1 rounded-full ${
                      link.supports_claim === true
                        ? "bg-green-400"
                        : link.supports_claim === false
                        ? "bg-red-400"
                        : "bg-gray-300"
                    }`}
                    style={{ width: `${Math.round(link.confidence * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
