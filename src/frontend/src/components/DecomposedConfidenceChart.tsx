"use client";

import type { DecomposedConfidence } from "@/types";

interface DecomposedConfidenceChartProps {
  confidence: DecomposedConfidence;
  size?: number;
}

const DIMENSIONS = [
  { key: "model_confidence", label: "Model", color: "#0891b2" },
  { key: "source_quality", label: "Source", color: "#059669" },
  { key: "evidence_breadth", label: "Evidence", color: "#7c3aed" },
  { key: "cross_reference_score", label: "Cross-ref", color: "#dc2626" },
  { key: "temporal_relevance", label: "Temporal", color: "#ea580c" },
] as const;

export default function DecomposedConfidenceChart({
  confidence,
  size = 200,
}: DecomposedConfidenceChartProps) {
  const cx = size / 2;
  const cy = size / 2;
  const maxR = size / 2 - 30;
  const levels = [0.2, 0.4, 0.6, 0.8, 1.0];
  const angleStep = (2 * Math.PI) / DIMENSIONS.length;

  function polarToCartesian(angle: number, radius: number) {
    return {
      x: cx + radius * Math.cos(angle - Math.PI / 2),
      y: cy + radius * Math.sin(angle - Math.PI / 2),
    };
  }

  // Grid rings
  const rings = levels.map((level) => {
    const r = maxR * level;
    const points = DIMENSIONS.map((_, i) => {
      const p = polarToCartesian(i * angleStep, r);
      return `${p.x},${p.y}`;
    }).join(" ");
    return points;
  });

  // Data polygon
  const dataPoints = DIMENSIONS.map((dim, i) => {
    const value = (confidence as any)[dim.key] ?? 0;
    const r = maxR * Math.min(value, 1);
    return polarToCartesian(i * angleStep, r);
  });

  const dataPath = dataPoints.map((p) => `${p.x},${p.y}`).join(" ");

  // Axis lines
  const axes = DIMENSIONS.map((_, i) => {
    const end = polarToCartesian(i * angleStep, maxR);
    return { x1: cx, y1: cy, x2: end.x, y2: end.y };
  });

  // Labels
  const labels = DIMENSIONS.map((dim, i) => {
    const p = polarToCartesian(i * angleStep, maxR + 18);
    const value = (confidence as any)[dim.key] ?? 0;
    return { ...p, label: dim.label, value };
  });

  const ariaScores = DIMENSIONS.map(dim => {
    const value = (confidence as any)[dim.key] ?? 0;
    return `${dim.label}: ${Math.round(value * 100)}%`;
  }).join(", ");

  return (
    <div className="flex flex-col items-center" role="img" aria-label={`Confidence radar chart. ${ariaScores}. Overall: ${Math.round((confidence.overall ?? 0) * 100)}%`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        {/* Grid rings */}
        {rings.map((points, i) => (
          <polygon
            key={i}
            points={points}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={i === rings.length - 1 ? 1.5 : 0.5}
          />
        ))}

        {/* Axes */}
        {axes.map((axis, i) => (
          <line
            key={i}
            x1={axis.x1}
            y1={axis.y1}
            x2={axis.x2}
            y2={axis.y2}
            stroke="#d1d5db"
            strokeWidth={0.5}
          />
        ))}

        {/* Data polygon */}
        <polygon
          points={dataPath}
          fill="rgba(8, 145, 178, 0.15)"
          stroke="#0891b2"
          strokeWidth={2}
        />

        {/* Data points */}
        {dataPoints.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={3}
            fill={DIMENSIONS[i].color}
            stroke="white"
            strokeWidth={1.5}
          />
        ))}

        {/* Labels */}
        {labels.map((l, i) => (
          <text
            key={i}
            x={l.x}
            y={l.y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="text-[9px] fill-gray-500 font-medium"
          >
            {l.label} ({Math.round(l.value * 100)}%)
          </text>
        ))}
      </svg>
      <p className="text-xs text-gray-400 mt-1">
        Overall: {Math.round((confidence.overall ?? 0) * 100)}%
      </p>
    </div>
  );
}
