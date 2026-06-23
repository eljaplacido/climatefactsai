"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  User,
  Bell,
  Languages,
  Shield,
  Loader2,
  Download,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Key,
  Copy,
  Check,
  Plus,
  AlertCircle,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface NotificationPrefs {
  email_daily_digest: boolean;
  email_breaking_alerts: boolean;
  email_weekly_report: boolean;
  push_new_articles: boolean;
}

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fi", label: "Suomi (Finnish)" },
  { code: "sv", label: "Svenska (Swedish)" },
  { code: "de", label: "Deutsch (German)" },
  { code: "fr", label: "Francais (French)" },
  { code: "es", label: "Espanol (Spanish)" },
];

interface ApiKeyInfo {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
}

interface ApiKeyCreated {
  id: string;
  name: string;
  api_key: string;
  scopes: string[];
  expires_at: string | null;
  warning: string;
}

export default function SettingsPage() {
  const { user, token, tier } = useAuth();

  const canManageKeys = ["professional", "pro", "enterprise"].includes(
    (tier || "").toLowerCase(),
  );

  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [apiKeysError, setApiKeysError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [creatingKey, setCreatingKey] = useState(false);
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [copiedNewKey, setCopiedNewKey] = useState(false);

  const fetchApiKeys = useCallback(async () => {
    if (!token) return;
    setApiKeysLoading(true);
    setApiKeysError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/api-keys`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to load API keys");
      }
      setApiKeys(await resp.json());
    } catch (e: any) {
      setApiKeysError(e.message || "Failed to load API keys");
    } finally {
      setApiKeysLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token || !canManageKeys) return;
    fetchApiKeys();
  }, [token, canManageKeys, fetchApiKeys]);

  async function handleCreateKey() {
    if (!newKeyName.trim() || !token) return;
    setCreatingKey(true);
    setApiKeysError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/api-keys`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name: newKeyName, scopes: ["read"] }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to create API key");
      }
      const data: ApiKeyCreated = await resp.json();
      setCreatedKey(data);
      setNewKeyName("");
      setShowCreateForm(false);
      fetchApiKeys();
    } catch (e: any) {
      setApiKeysError(e.message || "Failed to create API key");
    } finally {
      setCreatingKey(false);
    }
  }

  async function handleRevokeKey(keyId: string) {
    if (!token) return;
    setRevokingId(keyId);
    setApiKeysError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/api-keys/${keyId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to revoke API key");
      }
      fetchApiKeys();
    } catch (e: any) {
      setApiKeysError(e.message || "Failed to revoke API key");
    } finally {
      setRevokingId(null);
    }
  }

  function copyNewKey() {
    if (!createdKey) return;
    navigator.clipboard.writeText(createdKey.api_key);
    setCopiedNewKey(true);
    setTimeout(() => setCopiedNewKey(false), 2000);
  }

  const [notifications, setNotifications] = useState<NotificationPrefs>({
    email_daily_digest: true,
    email_breaking_alerts: true,
    email_weekly_report: false,
    push_new_articles: false,
  });
  const [language, setLanguage] = useState("en");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteText, setDeleteText] = useState("");
  const [deleting, setDeleting] = useState(false);

  function toggleNotification(key: keyof NotificationPrefs) {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await fetch(`${API_BASE}/api/user/preferences`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ notifications, language }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      // Silently handle - preferences are best-effort
    } finally {
      setSaving(false);
    }
  }

  async function handleExportData() {
    setExporting(true);
    try {
      const res = await fetch(`${API_BASE}/api/user/export-data`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "clilens-data-export.json";
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch {
      // Best-effort export
    } finally {
      setExporting(false);
    }
  }

  async function handleDeleteAccount() {
    if (deleteText !== "DELETE") return;
    setDeleting(true);
    try {
      await fetch(`${API_BASE}/api/user/account`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      window.location.href = "/";
    } catch {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage your account preferences and privacy settings.
        </p>
      </div>

      {/* API Keys Section */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <Key className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">API Keys</h2>
            <p className="text-xs text-gray-500">
              Generate and manage keys for programmatic API access
            </p>
          </div>
        </div>

        {!canManageKeys ? (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-4">
            <p className="text-sm text-amber-800">
              API keys require Professional tier.{" "}
              <Link
                href="/dashboard/subscription"
                className="font-semibold underline"
              >
                Upgrade to generate keys.
              </Link>
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {createdKey && (
              <div className="rounded-lg bg-teal-50 border border-teal-200 p-4">
                <p className="text-sm font-semibold text-teal-900 mb-1">
                  API key created — copy it now
                </p>
                <p className="text-xs text-teal-700 mb-3">
                  {createdKey.warning} This is the only time the full key will
                  be shown.
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-3 py-2 bg-white border border-teal-200 rounded-lg text-sm font-mono text-gray-800 break-all">
                    {createdKey.api_key}
                  </code>
                  <button
                    type="button"
                    onClick={copyNewKey}
                    className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors flex-shrink-0"
                  >
                    {copiedNewKey ? (
                      <>
                        <Check className="h-4 w-4" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4" />
                        Copy
                      </>
                    )}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => setCreatedKey(null)}
                  className="mt-3 text-xs text-teal-700 hover:underline"
                >
                  Dismiss
                </button>
              </div>
            )}

            {apiKeysError && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-3 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-red-700">{apiKeysError}</p>
              </div>
            )}

            {showCreateForm ? (
              <div className="rounded-lg border border-gray-200 p-4 space-y-3">
                <label className="block text-sm font-medium text-gray-700">
                  Key name
                </label>
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g. Production app"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleCreateKey}
                    disabled={!newKeyName.trim() || creatingKey}
                    className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    {creatingKey && <Loader2 className="h-4 w-4 animate-spin" />}
                    Create Key
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateForm(false);
                      setNewKeyName("");
                    }}
                    className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowCreateForm(true)}
                className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Generate New API Key
              </button>
            )}

            {apiKeysLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
              </div>
            ) : apiKeys.length === 0 ? (
              <div className="text-center py-8">
                <Key className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No API keys yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {apiKeys.map((key) => (
                  <div
                    key={key.id}
                    className="flex items-center justify-between rounded-lg border border-gray-200 p-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900">
                        {key.name}
                      </p>
                      <code className="text-xs text-gray-500 font-mono">
                        {key.key_prefix}
                      </code>
                      <div className="flex gap-3 mt-1 text-xs text-gray-400">
                        <span>
                          Created{" "}
                          {new Date(key.created_at).toLocaleDateString()}
                        </span>
                        <span>
                          {key.last_used_at
                            ? `Last used ${new Date(key.last_used_at).toLocaleDateString()}`
                            : "Never used"}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRevokeKey(key.id)}
                      disabled={revokingId === key.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-red-300 rounded-lg text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors flex-shrink-0"
                    >
                      {revokingId === key.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                      Revoke
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Profile Section */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <User className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Profile</h2>
            <p className="text-xs text-gray-500">
              Your account information
            </p>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              Full name
            </label>
            <input
              type="text"
              readOnly
              value={user?.full_name || ""}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              Email
            </label>
            <input
              type="email"
              readOnly
              value={user?.email || ""}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 cursor-not-allowed"
            />
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-3">
          Contact support to update your profile information.
        </p>
      </section>

      {/* Notification Preferences */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <Bell className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Notifications
            </h2>
            <p className="text-xs text-gray-500">
              Choose what updates you receive
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {([
            {
              key: "email_daily_digest" as const,
              label: "Daily digest",
              desc: "Receive a summary of top climate news every morning",
            },
            {
              key: "email_breaking_alerts" as const,
              label: "Breaking alerts",
              desc: "Get notified about high-impact climate events",
            },
            {
              key: "email_weekly_report" as const,
              label: "Weekly report",
              desc: "A weekly intelligence brief with trends and analysis",
            },
            {
              key: "push_new_articles" as const,
              label: "New article alerts",
              desc: "Notifications when articles match your saved topics",
            },
          ]).map(({ key, label, desc }) => (
            <div
              key={key}
              className="flex items-center justify-between py-2"
            >
              <div>
                <p className="text-sm font-medium text-gray-800">{label}</p>
                <p className="text-xs text-gray-500">{desc}</p>
              </div>
              <button
                type="button"
                onClick={() => toggleNotification(key)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  notifications[key] ? "bg-teal-600" : "bg-gray-300"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                    notifications[key] ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Language */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <Languages className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Language</h2>
            <p className="text-xs text-gray-500">
              Set your preferred display language
            </p>
          </div>
        </div>

        <select
          value={language}
          onChange={(e) => {
            setLanguage(e.target.value);
            setSaved(false);
          }}
          className="w-full sm:w-64 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
      </section>

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-teal-600 text-white rounded-lg font-medium text-sm hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save Preferences
        </button>
        {saved && (
          <span className="flex items-center gap-1.5 text-sm text-emerald-600">
            <CheckCircle2 className="h-4 w-4" />
            Saved
          </span>
        )}
      </div>

      {/* Data & Privacy */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <Shield className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Data & Privacy
            </h2>
            <p className="text-xs text-gray-500">
              Manage your data and account
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Export */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm font-medium text-gray-800">
                Export your data
              </p>
              <p className="text-xs text-gray-500">
                Download all your saved articles, search history, and
                preferences
              </p>
            </div>
            <button
              type="button"
              onClick={handleExportData}
              disabled={exporting}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Export
            </button>
          </div>

          {/* Delete */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-red-700">
                  Delete account
                </p>
                <p className="text-xs text-gray-500">
                  Permanently delete your account and all associated data
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(!showDeleteConfirm)}
                className="flex items-center gap-2 px-4 py-2 border border-red-300 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>

            {showDeleteConfirm && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-start gap-2 mb-3">
                  <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">
                    This action is <strong>irreversible</strong>. All your
                    data, saved articles, and search history will be
                    permanently deleted. Type <strong>DELETE</strong> to
                    confirm.
                  </p>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={deleteText}
                    onChange={(e) => setDeleteText(e.target.value)}
                    placeholder='Type "DELETE"'
                    className="flex-1 px-3 py-2 border border-red-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleDeleteAccount}
                    disabled={deleteText !== "DELETE" || deleting}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    {deleting && (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                    Confirm Delete
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
