"use client";

export default function SkeletonCard() {
  return (
    <div className="block bg-white rounded-xl shadow-sm overflow-hidden border-l-4 border-l-gray-200 border border-gray-200 animate-pulse">
      <div className="p-6">
        {/* Source + gauge */}
        <div className="flex items-start justify-between mb-3">
          <div className="h-4 w-32 bg-gray-200 rounded" />
          <div className="w-12 h-12 bg-gray-200 rounded-full" />
        </div>

        {/* Title */}
        <div className="space-y-2 mb-4">
          <div className="h-5 w-full bg-gray-200 rounded" />
          <div className="h-5 w-3/4 bg-gray-200 rounded" />
        </div>

        {/* Excerpt */}
        <div className="space-y-1.5 mb-4">
          <div className="h-3 w-full bg-gray-100 rounded" />
          <div className="h-3 w-full bg-gray-100 rounded" />
          <div className="h-3 w-2/3 bg-gray-100 rounded" />
        </div>

        {/* Tags */}
        <div className="flex gap-2 mb-4">
          <div className="h-5 w-16 bg-gray-100 rounded-full" />
          <div className="h-5 w-20 bg-gray-100 rounded-full" />
          <div className="h-5 w-14 bg-gray-100 rounded-full" />
        </div>

        {/* Meta row */}
        <div className="flex gap-4 mb-4">
          <div className="h-3 w-24 bg-gray-100 rounded" />
          <div className="h-3 w-20 bg-gray-100 rounded" />
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
          <div className="h-3 w-28 bg-gray-100 rounded" />
          <div className="flex items-center space-x-2">
            <div className="h-2 w-32 bg-gray-100 rounded-full" />
            <div className="h-3 w-8 bg-gray-100 rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}
