"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter, usePathname } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthUser {
  user_id: string;
  email: string;
  full_name: string;
  subscription_tier: string;
  is_verified: boolean;
  avatar_url?: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isLoggedIn: boolean;
  tier: string;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName: string,
  ) => Promise<{ requiresVerification: boolean }>;
  logout: () => void;
  refreshToken: () => Promise<string | null>;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiFetch(
  path: string,
  opts: RequestInit = {},
): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });
}

function storeTokens(access: string, refresh: string) {
  localStorage.setItem("clilens_token", access);
  localStorage.setItem("clilens_refresh_token", refresh);
}

function clearTokens() {
  localStorage.removeItem("clilens_token");
  localStorage.removeItem("clilens_refresh_token");
  localStorage.removeItem("clilens_user");
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // ---- refresh token ----
  const refreshToken = useCallback(async (): Promise<string | null> => {
    const refresh = localStorage.getItem("clilens_refresh_token");
    if (!refresh) return null;

    try {
      const resp = await apiFetch("/api/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });

      if (!resp.ok) {
        clearTokens();
        setUser(null);
        setToken(null);
        return null;
      }

      const data = await resp.json();
      const newToken = data.access_token as string;
      localStorage.setItem("clilens_token", newToken);
      if (data.refresh_token) {
        localStorage.setItem("clilens_refresh_token", data.refresh_token);
      }
      setToken(newToken);
      return newToken;
    } catch {
      clearTokens();
      setUser(null);
      setToken(null);
      return null;
    }
  }, []);

  // ---- fetch profile from /api/auth/me ----
  const fetchProfile = useCallback(
    async (accessToken: string): Promise<AuthUser | null> => {
      try {
        const resp = await apiFetch("/api/auth/me", {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!resp.ok) return null;
        const data = await resp.json();
        return {
          user_id: data.user_id,
          email: data.email,
          full_name: data.full_name || "",
          subscription_tier: data.subscription_tier || "freemium",
          is_verified: data.email_verified ?? data.is_verified ?? false,
          avatar_url: data.avatar_url,
        };
      } catch {
        return null;
      }
    },
    [],
  );

  // ---- initialise on mount ----
  useEffect(() => {
    async function init() {
      const stored = localStorage.getItem("clilens_token");
      if (!stored) {
        setLoading(false);
        return;
      }

      // Try current token first
      let profile = await fetchProfile(stored);
      if (profile) {
        setToken(stored);
        setUser(profile);
        setLoading(false);
        return;
      }

      // Token expired? attempt refresh
      const newToken = await refreshToken();
      if (newToken) {
        profile = await fetchProfile(newToken);
        if (profile) {
          setToken(newToken);
          setUser(profile);
        }
      }
      setLoading(false);
    }
    init();
  }, [fetchProfile, refreshToken]);

  // ---- auto-refresh before expiry (every 14 min for a 15-min token) ----
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(
      () => {
        refreshToken();
      },
      14 * 60 * 1000,
    );
    return () => clearInterval(interval);
  }, [token, refreshToken]);

  // ---- login ----
  const login = useCallback(
    async (email: string, password: string) => {
      const resp = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(
          err.detail || err.message || "Invalid email or password",
        );
      }
      const data = await resp.json();
      storeTokens(data.access_token, data.refresh_token);
      setToken(data.access_token);

      if (data.user) {
        const u: AuthUser = {
          user_id: data.user.user_id || data.user.id,
          email: data.user.email,
          full_name: data.user.full_name || "",
          subscription_tier: data.user.subscription_tier || "freemium",
          is_verified: data.user.email_verified ?? true,
          avatar_url: data.user.avatar_url,
        };
        setUser(u);
      } else {
        const profile = await fetchProfile(data.access_token);
        if (profile) setUser(profile);
      }
    },
    [fetchProfile],
  );

  // ---- register ----
  const register = useCallback(
    async (
      email: string,
      password: string,
      fullName: string,
    ): Promise<{ requiresVerification: boolean }> => {
      const resp = await apiFetch("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(
          err.detail || err.message || "Registration failed",
        );
      }
      const data = await resp.json();

      // Some backends return tokens immediately, some require email verification
      if (data.access_token) {
        storeTokens(data.access_token, data.refresh_token);
        setToken(data.access_token);
        const profile = await fetchProfile(data.access_token);
        if (profile) setUser(profile);
        return { requiresVerification: false };
      }

      return { requiresVerification: true };
    },
    [fetchProfile],
  );

  // ---- logout ----
  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setToken(null);
  }, []);

  const value: AuthContextValue = {
    user,
    token,
    isLoggedIn: !!user,
    tier: user?.subscription_tier || "freemium",
    loading,
    login,
    register,
    logout,
    refreshToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Protected Route wrapper
// ---------------------------------------------------------------------------

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isLoggedIn, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !isLoggedIn) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname || "/dashboard")}`);
    }
  }, [loading, isLoggedIn, router, pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
      </div>
    );
  }

  if (!isLoggedIn) return null;

  return <>{children}</>;
}
