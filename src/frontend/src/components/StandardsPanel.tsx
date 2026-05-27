"use client";

// Standards we check — Stage 5 / M6 explainer.
//
// Lists the 5 globally-recognized corporate sustainability reporting
// standards the platform assesses companies against. Each card has
// jurisdiction, scope, mandatory disclosure points, and an evidence URL.
//
// Data source: GET /api/companies/standards.

import { useEffect, useState } from "react";
import { ShieldCheck, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Standard {
  id: string;
  name: string;
  jurisdiction: string;
  effective_from: string;
  scope: string;
  mandatory_disclosure: string[];
  evidence_url: string;
}

export default function StandardsPanel() {
  const [standards, setStandards] = useState<Standard[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/companies/standards`)
      .then((r) => r.json())
      .then((d) => setStandards(d.standards || []))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  if (!loaded || standards.length === 0) return null;

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck className="h-5 w-5 text-teal-600" />
        <h2 className="text-base font-semibold text-gray-900">
          Standards we check ({standards.length})
        </h2>
      </div>
      <p className="text-xs text-gray-600 mb-3">
        Every company verdict on this page is assessed against these 5
        globally-recognized climate disclosure frameworks. Click any to
        see the mandatory disclosure points.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-2">
        {standards.map((s) => (
          <button
            key={s.id}
            onClick={() => setExpanded(expanded === s.id ? null : s.id)}
            className={`text-left text-xs border rounded-md px-2.5 py-2 transition-colors ${
              expanded === s.id
                ? "bg-teal-50 border-teal-300"
                : "bg-gray-50 border-gray-200 hover:border-teal-200"
            }`}
          >
            <div className="font-semibold text-gray-900">{s.id}</div>
            <div className="text-[10px] text-gray-500 mt-0.5">{s.jurisdiction}</div>
          </button>
        ))}
      </div>
      {expanded && (
        <div className="mt-4 bg-teal-50 border border-teal-200 rounded-md p-4">
          {(() => {
            const s = standards.find((x) => x.id === expanded);
            if (!s) return null;
            return (
              <>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div>
                    <h3 className="font-semibold text-gray-900">{s.name}</h3>
                    <p className="text-xs text-gray-600">
                      {s.jurisdiction} · effective from {s.effective_from}
                    </p>
                  </div>
                  <a
                    href={s.evidence_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-teal-700 hover:underline inline-flex items-center gap-1"
                  >
                    Source <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <p className="text-xs text-gray-700 mb-2">{s.scope}</p>
                <p className="text-xs font-semibold text-gray-800 mb-1">
                  Mandatory disclosure points:
                </p>
                <ul className="text-xs text-gray-700 space-y-0.5 list-disc list-inside">
                  {s.mandatory_disclosure.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </>
            );
          })()}
        </div>
      )}
    </section>
  );
}
