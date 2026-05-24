"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { TREND_LINE_COLORS } from "@/lib/climateColors";

interface TrendDataPoint {
  date: string;
  count: number;
  category?: string;
}

interface TrendChartProps {
  data: TrendDataPoint[];
  title?: string;
  height?: number;
}

function formatDateLabel(value: unknown): string {
  const dateStr = String(value ?? "");
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

export default function TrendChart({
  data,
  title,
  height = 300,
}: TrendChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-gray-400 py-8">
        No trend data available
      </div>
    );
  }

  return (
    <div>
      {title && (
        <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      )}
      <div
        role="img"
        aria-label={title ? `Line chart: ${title}` : "Article trend line chart"}
      >
        <ResponsiveContainer width="100%" height={height}>
          <LineChart
            data={data}
            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={{ fontSize: 12, fill: "#6b7280" }}
              axisLine={{ stroke: "#d1d5db" }}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 12, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
              width={40}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              contentStyle={{
                borderRadius: "8px",
                border: "1px solid #d1d5db",
                fontSize: "13px",
              }}
            />
            <Line
              type="monotone"
              dataKey="count"
              name="Articles"
              stroke={TREND_LINE_COLORS.topicA}
              strokeWidth={2}
              dot={{ r: 3, fill: "#0d9488", strokeWidth: 0 }}
              activeDot={{ r: 5, fill: "#0d9488", stroke: "#fff", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
