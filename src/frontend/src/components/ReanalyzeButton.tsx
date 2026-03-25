"use client";

interface ReanalyzeButtonProps {
  articleId: string;
  label: string;
  className?: string;
}

export default function ReanalyzeButton({ articleId, label, className }: ReanalyzeButtonProps) {
  return (
    <button
      onClick={async () => {
        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";
          await fetch(`${apiUrl}/api/articles/${articleId}/reanalyze`, { method: "POST" });
          window.location.reload();
        } catch {
          alert("Failed to trigger analysis. Please try again.");
        }
      }}
      className={className}
    >
      {label}
    </button>
  );
}
