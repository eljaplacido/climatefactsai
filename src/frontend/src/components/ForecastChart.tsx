"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface ForecastDataPoint {
  date: string;
  temperature: number;
  precipitation: number;
}

interface ForecastChartProps {
  data: ForecastDataPoint[];
  title?: string;
  height?: number;
  unit?: string;
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

export default function ForecastChart({
  data,
  title,
  height = 320,
  unit,
}: ForecastChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-gray-400 py-8">
        No forecast data to chart
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
        aria-label={
          title
            ? `Forecast chart: ${title}`
            : "Combined temperature and precipitation forecast chart"
        }
      >
        <ResponsiveContainer width="100%" height={height}>
          <ComposedChart
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
              yAxisId="temp"
              orientation="left"
              tick={{ fontSize: 12, fill: "#ea580c" }}
              axisLine={false}
              tickLine={false}
              width={45}
              label={{
                value: unit || "\u00B0C",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 12, fill: "#ea580c" },
              }}
            />
            <YAxis
              yAxisId="precip"
              orientation="right"
              tick={{ fontSize: 12, fill: "#2563eb" }}
              axisLine={false}
              tickLine={false}
              width={45}
              label={{
                value: "mm",
                angle: 90,
                position: "insideRight",
                style: { fontSize: 12, fill: "#2563eb" },
              }}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              contentStyle={{
                borderRadius: "8px",
                border: "1px solid #d1d5db",
                fontSize: "13px",
              }}
              formatter={(value: unknown, name: unknown) => {
                const v = String(value ?? "");
                const n = String(name ?? "");
                if (n === "Temperature") return [`${v} ${unit || "\u00B0C"}`, n];
                if (n === "Precipitation") return [`${v} mm`, n];
                return [v, n];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
            />
            <Bar
              yAxisId="precip"
              dataKey="precipitation"
              name="Precipitation"
              fill="#93c5fd"
              radius={[3, 3, 0, 0]}
              barSize={20}
            />
            <Line
              yAxisId="temp"
              type="monotone"
              dataKey="temperature"
              name="Temperature"
              stroke="#ea580c"
              strokeWidth={2}
              dot={{ r: 3, fill: "#ea580c", strokeWidth: 0 }}
              activeDot={{ r: 5, fill: "#ea580c", stroke: "#fff", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
