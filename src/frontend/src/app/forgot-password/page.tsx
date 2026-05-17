"use client";

import { useState } from "react";
import Link from "next/link";
import { Globe, Mail, Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Something went wrong. Please try again.");
      }

      setSent(true);
    } catch (err: any) {
      setError(err.message || "Failed to send reset email.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-600 via-teal-700 to-emerald-800 px-4 py-12">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="bg-white/20 backdrop-blur p-2.5 rounded-xl">
              <Globe className="h-7 w-7 text-white" />
            </div>
            <div className="text-left">
              <p className="text-2xl font-bold text-white leading-tight">
                Climatefacts.ai
              </p>
              <p className="text-xs text-teal-200 leading-tight">
                Climate Intelligence
              </p>
            </div>
          </Link>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          {sent ? (
            /* Success state */
            <div className="text-center">
              <div className="mx-auto w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center mb-4">
                <CheckCircle2 className="h-7 w-7 text-emerald-600" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                Check your email
              </h1>
              <p className="text-sm text-gray-500 mb-6">
                If an account exists for <strong>{email}</strong>, we sent a
                password reset link. It may take a minute to arrive.
              </p>
              <Link
                href="/login"
                className="inline-flex items-center gap-2 text-sm font-semibold text-teal-600 hover:text-teal-700"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Sign In
              </Link>
            </div>
          ) : (
            /* Form state */
            <>
              <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
                Reset your password
              </h1>
              <p className="text-sm text-gray-500 text-center mb-6">
                Enter your email address and we&apos;ll send you a link to
                reset your password.
              </p>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Email address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                      className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading || !email}
                  className="w-full py-2.5 bg-teal-600 text-white rounded-lg font-medium text-sm hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                  Send Reset Link
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-gray-500">
                Remember your password?{" "}
                <Link
                  href="/login"
                  className="text-teal-600 font-semibold hover:text-teal-700"
                >
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
