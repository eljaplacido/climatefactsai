"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!searchParams) return;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const errorParam = searchParams.get("error");

    if (errorParam) { setError(`OAuth error: ${errorParam}`); return; }
    if (!code || !state) { setError("Missing authorization code"); return; }

    // Verify the returned state matches the one we stashed before redirecting
    // to the provider — protects against CSRF / code-injection. Look up the
    // provider via sessionStorage instead of trusting whatever came back in
    // the state field.
    let expectedState: string | null = null;
    let provider: string | null = null;
    let postLoginRedirect = "/";
    try {
      expectedState = sessionStorage.getItem("oauth_state");
      provider = sessionStorage.getItem("oauth_provider");
      postLoginRedirect = sessionStorage.getItem("oauth_redirect") || "/";
    } catch {
      // sessionStorage unavailable — degrade with a clear error.
    }

    if (!expectedState || !provider) {
      setError(
        "OAuth session expired. Please start sign-in again from the login page."
      );
      return;
    }
    if (state !== expectedState) {
      setError("OAuth state mismatch (possible CSRF). Please try again.");
      return;
    }

    // Clear one-shot storage so a reload of this URL can't replay the flow.
    try {
      sessionStorage.removeItem("oauth_state");
      sessionStorage.removeItem("oauth_provider");
      sessionStorage.removeItem("oauth_redirect");
    } catch { /* ignore */ }

    async function exchangeCode() {
      try {
        const resp = await fetch(`${API_URL}/api/auth/oauth/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code,
            redirect_uri: `${window.location.origin}/auth/callback`,
            provider,
            state,
          }),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.detail || "OAuth callback failed");
        }
        const tokens = await resp.json();
        // NOTE: localStorage is the current pattern; migrating to httpOnly
        // cookies is tracked as security P0 S5 (Sprint 1 follow-up).
        localStorage.setItem("clilens_token", tokens.access_token);
        localStorage.setItem("clilens_refresh", tokens.refresh_token);
        localStorage.setItem("clilens_user", JSON.stringify({
          user_id: tokens.user_id, email: tokens.email, full_name: tokens.full_name, avatar_url: tokens.avatar_url,
        }));
        router.push(postLoginRedirect);
      } catch (err: any) { setError(err.message || "Authentication failed"); }
    }
    exchangeCode();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md text-center">
          <h2 className="text-xl font-bold text-red-600 mb-3">Authentication Failed</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <button onClick={() => router.push("/")} className="px-6 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700">Return to Home</button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <Loader2 className="h-10 w-10 animate-spin text-teal-600 mx-auto mb-4" />
        <p className="text-gray-600">Completing sign-in...</p>
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="h-10 w-10 animate-spin text-teal-600" />
      </div>
    }>
      <CallbackHandler />
    </Suspense>
  );
}
