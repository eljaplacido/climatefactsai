"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

interface RegionData {
  region: string;
  count: number;
}

interface CredibilityData {
  level: string;
  count: number;
}

interface AnalyticsSummaryChartProps {
  articlesByRegion: RegionData[];
  credibilityDistribution: CredibilityData[];
}

const CREDIBILITY_COLORS: Record<string, string> = {
  HIGH: "#10b981",
  MEDIUM: "#f59e0b",
  LOW: "#ef4444",
};

function getCredibilityColor(level: string): string {
  return CREDIBILITY_COLORS[level.toUpperCase()] || "#9ca3af";
}

export default function AnalyticsSummaryChart({
  articlesByRegion,
  credibilityDistribution,
}: AnalyticsSummaryChartProps) {
  const hasRegionData = articlesByRegion && articlesByRegion.length > 0;
  const hasCredibilityData =
    credibilityDistribution && credibilityDistribution.length > 0;

  if (!hasRegionData && !hasCredibilityData) {
    return (
      <div className="flex items-center justify-center text-sm text-gray-400 py-8">
        No analytics data available
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Horizontal bar chart for articles by region */}
      {hasRegionData && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Articles by Region
          </h3>
          <div
            role="img"
            aria-label="Horizontal bar chart showing article count by region"
          >
            <ResponsiveContainer width="100%" height={Math.max(200, articlesByRegion.length * 36)}>
              <BarChart
                data={articlesByRegion}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e5e7eb"
                  horizontal={false}
                />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 12, fill: "#6b7280" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="region"
                  tick={{ fontSize: 12, fill: "#374151" }}
                  axisLine={false}
                  tickLine={false}
                  width={80}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #d1d5db",
                    fontSize: "13px",
                  }}
                />
                <Bar
                  dataKey="count"
                  name="Articles"
                  fill="#0d9488"
                  radius={[0, 4, 4, 0]}
                  barSize={20}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Donut chart for credibility distribution */}
      {hasCredibilityData && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Credibility Distribution
          </h3>
          <div
            role="img"
            aria-label="Donut chart showing credibility level distribution"
          >
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={credibilityDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  dataKey="count"
                  nameKey="level"
                  paddingAngle={3}
                  label={({ name, value }: { name?: string; value?: number }) =>
                    `${name ?? ""}: ${value ?? 0}`
                  }
                  labelLine={{ stroke: "#9ca3af" }}
                >
                  {credibilityDistribution.map((entry) => (
                    <Cell
                      key={entry.level}
                      fill={getCredibilityColor(entry.level)}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #d1d5db",
                    fontSize: "13px",
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
                  formatter={(value: string) => (
                    <span style={{ color: "#374151" }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
