"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Play, Pause, Calendar } from "lucide-react";

interface MapTimelineProps {
  startDate?: string; // YYYY-MM format, default "2024-01"
  currentDate: string; // YYYY-MM
  onChange: (date: string) => void;
}

function getMonthsBetween(start: string, end: string): string[] {
  const months: string[] = [];
  const [startYear, startMonth] = start.split("-").map(Number);
  const [endYear, endMonth] = end.split("-").map(Number);

  let y = startYear;
  let m = startMonth;

  while (y < endYear || (y === endYear && m <= endMonth)) {
    months.push(`${y}-${String(m).padStart(2, "0")}`);
    m++;
    if (m > 12) {
      m = 1;
      y++;
    }
  }
  return months;
}

function formatMonth(ym: string): string {
  const [y, m] = ym.split("-");
  const date = new Date(Number(y), Number(m) - 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

export default function MapTimeline({
  startDate = "2024-01",
  currentDate,
  onChange,
}: MapTimelineProps) {
  const now = new Date();
  const endDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  const months = useMemo(() => getMonthsBetween(startDate, endDate), [startDate, endDate]);
  const currentIndex = months.indexOf(currentDate);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const advanceMonth = useCallback(() => {
    const idx = months.indexOf(currentDate);
    if (idx < months.length - 1) {
      onChange(months[idx + 1]);
    } else {
      // Loop back to start
      setPlaying(false);
    }
  }, [currentDate, months, onChange]);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(advanceMonth, 1500);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [playing, advanceMonth]);

  function handleSliderChange(e: React.ChangeEvent<HTMLInputElement>) {
    const idx = Number(e.target.value);
    if (months[idx]) {
      onChange(months[idx]);
    }
  }

  function togglePlay() {
    // If at the end, restart from beginning
    if (currentIndex >= months.length - 1) {
      onChange(months[0]);
    }
    setPlaying(!playing);
  }

  if (months.length < 2) return null;

  return (
    <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-[999] w-full max-w-xl px-4">
      <div className="bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700 shadow-xl px-4 py-3">
        <div className="flex items-center gap-3">
          {/* Play/Pause */}
          <button
            type="button"
            onClick={togglePlay}
            className="p-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-slate-300 hover:text-slate-100 transition-colors flex-shrink-0"
            title={playing ? "Pause" : "Play"}
          >
            {playing ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </button>

          {/* Slider */}
          <div className="flex-1 relative">
            <input
              type="range"
              min={0}
              max={months.length - 1}
              value={currentIndex >= 0 ? currentIndex : 0}
              onChange={handleSliderChange}
              className="w-full h-1.5 bg-slate-600 rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none
                [&::-webkit-slider-thumb]:w-4
                [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full
                [&::-webkit-slider-thumb]:bg-teal-500
                [&::-webkit-slider-thumb]:border-2
                [&::-webkit-slider-thumb]:border-slate-800
                [&::-webkit-slider-thumb]:shadow-md
                [&::-webkit-slider-thumb]:cursor-pointer
                [&::-moz-range-thumb]:w-4
                [&::-moz-range-thumb]:h-4
                [&::-moz-range-thumb]:rounded-full
                [&::-moz-range-thumb]:bg-teal-500
                [&::-moz-range-thumb]:border-2
                [&::-moz-range-thumb]:border-slate-800
                [&::-moz-range-thumb]:cursor-pointer"
            />
            {/* Track progress overlay */}
            <div
              className="absolute top-0 left-0 h-1.5 bg-teal-500/40 rounded-full pointer-events-none mt-[9px]"
              style={{
                width: `${((currentIndex >= 0 ? currentIndex : 0) / (months.length - 1)) * 100}%`,
              }}
            />
          </div>

          {/* Current date display */}
          <div className="flex items-center gap-1.5 bg-slate-700 rounded-lg px-3 py-1.5 flex-shrink-0 min-w-[120px] justify-center">
            <Calendar className="h-3.5 w-3.5 text-teal-400" />
            <span className="text-sm font-medium text-slate-200">
              {formatMonth(currentDate)}
            </span>
          </div>
        </div>

        {/* Tick marks for key dates */}
        <div className="flex justify-between px-10 mt-1">
          <span className="text-[9px] text-slate-500">
            {formatMonth(months[0])}
          </span>
          {months.length > 4 && (
            <span className="text-[9px] text-slate-500">
              {formatMonth(months[Math.floor(months.length / 2)])}
            </span>
          )}
          <span className="text-[9px] text-slate-500">
            {formatMonth(months[months.length - 1])}
          </span>
        </div>
      </div>
    </div>
  );
}
