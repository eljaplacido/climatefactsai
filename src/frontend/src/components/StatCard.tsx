"use client";

import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: number | string;
  icon: LucideIcon;
  color?: "blue" | "green" | "purple" | "orange";
}

const COLOR_MAP: Record<NonNullable<StatCardProps["color"]>, string> = {
  blue: "bg-blue-50 text-blue-700",
  green: "bg-emerald-50 text-emerald-700",
  purple: "bg-purple-50 text-purple-700",
  orange: "bg-orange-50 text-orange-700",
};

function StatCard({ title, value, icon: Icon, color = "blue" }: StatCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-3xl font-semibold text-gray-900 mt-2">{value}</p>
        </div>
        <div className={`p-3 rounded-full ${COLOR_MAP[color]}`}>
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </div>
  );
}

export default StatCard;
