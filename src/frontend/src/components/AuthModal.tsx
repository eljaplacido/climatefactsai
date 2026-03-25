"use client";

import { useState, useCallback } from "react";
import { X, Chrome, Monitor, Eye, EyeOff, Loader2 } from "lucide-react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (tokens: { access_token: string; email: string }) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
const MS_CLIENT_ID = process.env.NEXT_PUBLIC_MICROSOFT_CLIENT_ID || "";

export default function AuthModal({ isOpen, onClose, onAuthSuccess }: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEmailAuth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body: Record<string, string> = { email, password };
      if (mode === "register") body.full_name = fullName;

      const resp = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || "Authentication failed");
      }
      const tokens = await resp.json();
      localStorage.setItem("clilens_token", tokens.access_token);
      localStorage.setItem("clilens_refresh", tokens.refresh_token);
      onAuthSuccess({ access_token: tokens.access_token, email });
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  }, [mode, email, password, fullName, onAuthSuccess]);

  const handleOAuth = useCallback((provider: "google" | "microsoft") => {
    const redirectUri = `${window.location.origin}/auth/callback`;
    let authUrl: string;
    if (provider === "google") {
      authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=openid%20email%20profile&state=${provider}&access_type=offline&prompt=consent`;
    } else {
      authUrl = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=${MS_CLIENT_ID}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=openid%20profile%20email%20User.Read&state=${provider}`;
    }
    window.location.href = authUrl;
  }, []);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl w-full max-w-md mx-4 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900">
            {mode === "login" ? "Sign in to CliLens" : "Create account"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>

        <div className="space-y-3 mb-6">
          <button onClick={() => handleOAuth("google")} disabled={!GOOGLE_CLIENT_ID}
            className="w-full flex items-center gap-3 px-4 py-2.5 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed">
            <Chrome className="h-5 w-5 text-blue-500" />
            {GOOGLE_CLIENT_ID ? "Continue with Google" : "Google Sign-in (configure credentials)"}
          </button>
          <button onClick={() => handleOAuth("microsoft")} disabled={!MS_CLIENT_ID}
            className="w-full flex items-center gap-3 px-4 py-2.5 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed">
            <Monitor className="h-5 w-5 text-blue-600" />
            {MS_CLIENT_ID ? "Continue with Microsoft" : "Microsoft Sign-in (configure credentials)"}
          </button>
        </div>

        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400">or use email</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>

        {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>}

        <div className="space-y-3">
          {mode === "register" && (
            <input type="text" placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none" />
          )}
          <input type="email" placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none" />
          <div className="relative">
            <input type={showPassword ? "text" : "password"} placeholder="Password" value={password}
              onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleEmailAuth()}
              className="w-full px-4 py-2.5 pr-10 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none" />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <button onClick={handleEmailAuth} disabled={loading || !email || !password}
            className="w-full py-2.5 bg-teal-600 text-white rounded-lg font-medium text-sm hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </div>

        <p className="mt-4 text-center text-sm text-gray-500">
          {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
          <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
            className="text-teal-600 font-medium hover:text-teal-700">
            {mode === "login" ? "Sign up" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
