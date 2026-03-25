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

    async function exchangeCode() {
      try {
        const resp = await fetch(`${API_URL}/api/auth/oauth/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, redirect_uri: `${window.location.origin}/auth/callback`, provider: state }),
        });
        if (!resp.ok) { const data = await resp.json(); throw new Error(data.detail || "OAuth callback failed"); }
        const tokens = await resp.json();
        localStorage.setItem("clilens_token", tokens.access_token);
        localStorage.setItem("clilens_refresh", tokens.refresh_token);
        localStorage.setItem("clilens_user", JSON.stringify({
          user_id: tokens.user_id, email: tokens.email, full_name: tokens.full_name, avatar_url: tokens.avatar_url,
        }));
        router.push("/");
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
