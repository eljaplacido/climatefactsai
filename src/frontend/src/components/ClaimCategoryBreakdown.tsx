"use client";

import { Beaker, BarChart3, Scale, Eye, TrendingUp } from "lucide-react";

interface ClaimCategoryBreakdownProps {
  categories: Record<string, number>;
}

const CATEGORY_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  scientific_causal: { label: "Scientific", color: "#0891b2", icon: Beaker },
  statistical: { label: "Statistical", color: "#7c3aed", icon: BarChart3 },
  policy: { label: "Policy", color: "#059669", icon: Scale },
  anecdotal: { label: "Anecdotal", color: "#ea580c", icon: Eye },
  predictive: { label: "Predictive", color: "#dc2626", icon: TrendingUp },
};

export default function ClaimCategoryBreakdown({ categories }: ClaimCategoryBreakdownProps) {
  const entries = Object.entries(categories).filter(([_, count]) => count > 0);
  if (entries.length === 0) return null;

  const total = entries.reduce((sum, [_, count]) => sum + count, 0);

  // SVG donut chart
  const size = 120;
  const cx = size / 2;
  const cy = size / 2;
  const outerR = 50;
  const innerR = 30;

  let cumulativeAngle = -Math.PI / 2;
  const segments = entries.map(([cat, count]) => {
    const fraction = count / total;
    const startAngle = cumulativeAngle;
    const endAngle = cumulativeAngle + fraction * 2 * Math.PI;
    cumulativeAngle = endAngle;

    const config = CATEGORY_CONFIG[cat] || { label: cat, color: "#6b7280", icon: BarChart3 };

    const x1Outer = cx + outerR * Math.cos(startAngle);
    const y1Outer = cy + outerR * Math.sin(startAngle);
    const x2Outer = cx + outerR * Math.cos(endAngle);
    const y2Outer = cy + outerR * Math.sin(endAngle);
    const x1Inner = cx + innerR * Math.cos(endAngle);
    const y1Inner = cy + innerR * Math.sin(endAngle);
    const x2Inner = cx + innerR * Math.cos(startAngle);
    const y2Inner = cy + innerR * Math.sin(startAngle);

    const largeArcFlag = fraction > 0.5 ? 1 : 0;

    const d = [
      `M ${x1Outer} ${y1Outer}`,
      `A ${outerR} ${outerR} 0 ${largeArcFlag} 1 ${x2Outer} ${y2Outer}`,
      `L ${x1Inner} ${y1Inner}`,
      `A ${innerR} ${innerR} 0 ${largeArcFlag} 0 ${x2Inner} ${y2Inner}`,
      "Z",
    ].join(" ");

    return { cat, count, fraction, d, config };
  });

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {segments.map((seg) => (
          <path key={seg.cat} d={seg.d} fill={seg.config.color} opacity={0.85} />
        ))}
        <text x={cx} y={cy - 4} textAnchor="middle" className="text-lg font-bold fill-gray-900">
          {total}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" className="text-[9px] fill-gray-500">
          claims
        </text>
      </svg>

      <div className="space-y-1.5">
        {segments.map((seg) => {
          const Icon = seg.config.icon;
          return (
            <div key={seg.cat} className="flex items-center gap-2 text-xs">
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: seg.config.color }} />
              <Icon className="h-3 w-3 text-gray-400" />
              <span className="text-gray-600">{seg.config.label}</span>
              <span className="font-semibold text-gray-800">{seg.count}</span>
              <span className="text-gray-400">({Math.round(seg.fraction * 100)}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
