"use client";

import { useEffect, useState } from "react";
import { getLastTrace, subscribeTrace } from "@/lib/trace";

export default function TraceDebug() {
  const [trace, setTrace] = useState(getLastTrace());

  useEffect(() => {
    return subscribeTrace(setTrace);
  }, []);

  if (!trace.requestId && !trace.traceId) return null;

  const jaegerUrl = trace.traceId ? `http://localhost:5686/trace/${trace.traceId}` : null;

  return (
    <div className="fixed bottom-3 right-3 z-50 text-xs bg-white/90 backdrop-blur border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
      {trace.requestId && (
        <div className="text-gray-700">
          <span className="font-medium">Request</span>: <span className="font-mono">{trace.requestId}</span>
        </div>
      )}
      {trace.traceId && (
        <div className="text-gray-700">
          <span className="font-medium">Trace</span>:{" "}
          {jaegerUrl ? (
            <a className="font-mono text-clilens-teal-700 hover:underline" href={jaegerUrl} target="_blank" rel="noreferrer">
              {trace.traceId}
            </a>
          ) : (
            <span className="font-mono">{trace.traceId}</span>
          )}
        </div>
      )}
    </div>
  );
}

