"use client";

interface LoadingSpinnerProps {
  text?: string;
}

function LoadingSpinner({ text }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center space-y-4">
      <div className="w-12 h-12 border-4 border-clilens-primary/30 border-t-clilens-primary rounded-full animate-spin" />
      {text && <p className="text-sm text-gray-600">{text}</p>}
    </div>
  );
}

export default LoadingSpinner;
