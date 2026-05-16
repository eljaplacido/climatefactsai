"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { X, Search } from "lucide-react";

const DISMISS_KEY = "clilens_login_prompt_dismissed";

export default function LoginPrompt() {
  const [dismissed, setDismissed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(DISMISS_KEY) === "1");
    } catch {
      // ignore if localStorage is unavailable
    }
    setHydrated(true);
  }, []);

  const handleDismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // ignore
    }
    setDismissed(true);
  };

  if (!hydrated || dismissed) return null;

  return (
    <div className="relative bg-emerald-50 border border-emerald-200 rounded-lg p-4 shadow-sm">
      <button
        onClick={handleDismiss}
        className="absolute top-2 right-2 text-emerald-400 hover:text-emerald-600 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="flex items-start gap-3 pr-6">
        <div className="mt-0.5 bg-emerald-100 rounded-full p-1.5">
          <Search className="h-4 w-4 text-emerald-600" />
        </div>
        <div>
          <p className="text-sm font-medium text-emerald-900">
            Sign in to save your searches, bookmark articles, and access your history.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <Link
              href="/login"
              className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-md transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/signup"
              className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium text-teal-700 bg-white border border-teal-200 hover:bg-teal-50 rounded-md transition-colors"
            >
              Create Account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
