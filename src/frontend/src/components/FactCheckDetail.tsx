"use client";

import { useState } from "react";
import clsx from "clsx";
import { AlertCircle, CheckCircle, HelpCircle, Info, XCircle } from "lucide-react";
import Markdown from "./Markdown";

interface FactCheckDetailProps {
  claim: string;
  status: string;
  confidence: number;
  justification: string;
  evidence?: any;
}

const formatConfidence = (confidence: number) => Math.round((confidence ?? 0) * 100);

const getExternalEvidence = (evidence: any) => {
  if (!evidence || typeof evidence !== "object") {
    return {};
  }
  if (Array.isArray(evidence)) {
    return {};
  }
  return evidence.external ?? {};
};

const getStatusConfig = (status: string) => {
  switch (status) {
    case "VERIFIED":
      return {
        icon: CheckCircle,
        color: "text-emerald-600",
        bg: "bg-emerald-50",
        border: "border-emerald-200",
        label: "Verified",
        description: "Claim verified against trusted sources.",
      };
    case "PARTIALLY_VERIFIED":
      return {
        icon: AlertCircle,
        color: "text-yellow-600",
        bg: "bg-yellow-50",
        border: "border-yellow-200",
        label: "Partially verified",
        description: "Claim is partly accurate and requires context.",
      };
    case "DISPUTED":
      return {
        icon: AlertCircle,
        color: "text-orange-600",
        bg: "bg-orange-50",
        border: "border-orange-200",
        label: "Disputed",
        description: "Conflicting sources or interpretations detected.",
      };
    case "FALSE":
      return {
        icon: XCircle,
        color: "text-red-600",
        bg: "bg-red-50",
        border: "border-red-200",
        label: "False",
        description: "Claim has been shown to be incorrect.",
      };
    default:
      return {
        icon: Info,
        color: "text-gray-600",
        bg: "bg-gray-50",
        border: "border-gray-200",
        label: "Not yet checked",
        description: "Fact-checking is in progress or not available.",
      };
  }
};

function FactCheckDetail({ claim, status, confidence, justification, evidence }: FactCheckDetailProps) {
  const [showModal, setShowModal] = useState(false);

  const config = getStatusConfig(status);
  const Icon = config.icon;

  const sourceList = (() => {
    if (!evidence) {
      return [] as string[];
    }
    if (Array.isArray(evidence)) {
      return evidence as string[];
    }
    if (typeof evidence === "object" && Array.isArray(evidence.sources)) {
      return evidence.sources as string[];
    }
    return [] as string[];
  })();

  const externalEvidence = getExternalEvidence(evidence);

  return (
    <>
      <div className="flex items-start space-x-3 p-4 bg-white rounded-lg border border-gray-200">
        <div
          className={clsx(
            "flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center",
            config.bg,
            config.color,
            config.border,
          )}
        >
          <Icon className="h-5 w-5" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className={clsx("text-sm font-semibold", config.color)}>{config.label}</span>
            <span className="text-sm text-gray-500">{formatConfidence(confidence)}% confidence</span>
          </div>

          <p className="text-sm text-gray-700 line-clamp-2">{claim}</p>

          <button
            onClick={() => setShowModal(true)}
            className="mt-2 inline-flex items-center text-sm text-clilens-primary hover:text-clilens-teal-600 font-medium"
          >
            <HelpCircle className="h-4 w-4 mr-1" />
            View verification details
          </button>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6 border-b">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0">
                    <Icon className={clsx("h-8 w-8", config.color)} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">{config.label}</h3>
                    <p className="text-sm text-gray-600 mt-1">{config.description}</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
                  aria-label="Close fact check details"
                >
                  x
                </button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Claim reviewed</h4>
                <p className="text-gray-900 bg-gray-50 p-3 rounded-lg">"{claim}"</p>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Confidence level</h4>
                <div className="flex items-center space-x-3">
                  <div className="flex-1 bg-gray-200 rounded-full h-3">
                    <div
                      className="h-3 rounded-full bg-gradient-to-r from-clilens-primary to-clilens-teal-600"
                      style={{ width: `${formatConfidence(confidence)}%` }}
                    />
                  </div>
                  <span className="text-lg font-bold text-gray-900">{formatConfidence(confidence)}%</span>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Confidence derived from Perplexity-assisted reasoning and cross-checks with reference datasets.
                </p>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Summary</h4>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <Markdown content={justification} />
                </div>
              </div>

              {sourceList.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Evidence sources</h4>
                  <ul className="space-y-2">
                    {sourceList.slice(0, 5).map((source, idx) => {
                      const truncated = source.length > 80 ? `${source.substring(0, 80)}...` : source;
                      return (
                        <li key={idx} className="flex items-start space-x-2 text-sm">
                          <span className="text-clilens-primary font-semibold">{idx + 1}.</span>
                          <a
                            href={source}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-clilens-primary hover:underline break-all"
                          >
                            {truncated}
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {externalEvidence && Object.keys(externalEvidence).length > 0 && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
                  <h4 className="text-sm font-semibold text-gray-700">Supplementary data</h4>
                  {externalEvidence.climatecheck && (
                    <div className="text-xs text-gray-600">
                      <span className="font-semibold text-emerald-700">ClimateCheck:</span>
                      {' '}
                      Hazard {externalEvidence.climatecheck.hazardType ?? "n/a"} at risk score {externalEvidence.climatecheck.riskScore ?? "-"}/100
                    </div>
                  )}
                  {externalEvidence.noaa && (
                    <div className="text-xs text-gray-600">
                      <span className="font-semibold text-blue-700">NOAA:</span>
                      {' '}
                      {(externalEvidence.noaa.results?.length ?? 0)} observations from dataset {externalEvidence.noaa.dataType ?? "temperature"}
                    </div>
                  )}
                  {externalEvidence.nasa && (
                    <div className="text-xs text-gray-600">
                      <span className="font-semibold text-purple-700">NASA:</span>
                      {' '}
                      Surface temperature {externalEvidence.nasa.temperature ?? "n/a"} deg C ({externalEvidence.nasa.timestamp ?? "timestamp unavailable"})
                    </div>
                  )}
                </div>
              )}

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start space-x-2">
                  <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-blue-900 mb-1">How we verify claims</h4>
                    <p className="text-xs text-blue-800">
                      We combine Perplexity-assisted research with official datasets (ClimateCheck, NOAA, NASA) to confirm climate-related statements.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t p-4 bg-gray-50 flex justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 bg-clilens-primary text-white rounded-lg hover:bg-clilens-teal-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default FactCheckDetail;
