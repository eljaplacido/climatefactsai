"use client";

import { useEffect, useState } from "react";
import {
  CreditCard,
  Crown,
  Zap,
  Building2,
  User,
  Check,
  Loader2,
  AlertTriangle,
  ArrowUpRight,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface Subscription {
  tier: string;
  status: string;
  price?: number;
  current_period_start?: string;
  current_period_end?: string;
}

interface PaymentRecord {
  payment_id: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
}

const PLANS = [
  {
    id: "freemium",
    name: "Free",
    price: 0,
    icon: User,
    features: [
      "5 articles per day",
      "Basic search",
      "Map view",
      "Community features",
    ],
  },
  {
    id: "basic",
    name: "Basic",
    price: 9.99,
    icon: Zap,
    features: [
      "50 articles per day",
      "Deep search",
      "Bookmarks & history",
      "Email digests",
      "50 searches per day",
    ],
  },
  {
    id: "professional",
    name: "Professional",
    price: 29.99,
    icon: Crown,
    popular: true,
    features: [
      "Unlimited articles",
      "API access (1,000/day)",
      "Priority analysis",
      "Custom feeds",
      "URL analysis (20/mo)",
      "Unlimited searches",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 99.99,
    icon: Building2,
    features: [
      "Everything in Professional",
      "Team features",
      "Dedicated SLA",
      "Custom integrations",
      "Unlimited URL analysis",
      "Unlimited API calls",
    ],
  },
];

export default function SubscriptionPage() {
  const { token, tier } = useAuth();
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [payments, setPayments] = useState<PaymentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);

  useEffect(() => {
    if (!token) return;

    async function fetchData() {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [subResp, histResp] = await Promise.all([
          fetch(`${API_URL}/api/subscription/current`, { headers }),
          fetch(`${API_URL}/api/subscription/history`, { headers }),
        ]);

        if (subResp.ok) {
          setSubscription(await subResp.json());
        }
        if (histResp.ok) {
          const data = await histResp.json();
          setPayments(data.payments || data || []);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [token]);

  async function handleUpgrade(planId: string) {
    if (!token) return;
    setActionLoading(true);
    try {
      const resp = await fetch(`${API_URL}/api/subscription/upgrade`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ tier: planId }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setSubscription(data);
        window.location.reload();
      }
    } catch {
      // ignore
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!token) return;
    setActionLoading(true);
    try {
      const resp = await fetch(`${API_URL}/api/subscription/cancel`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        setShowCancelDialog(false);
        window.location.reload();
      }
    } catch {
      // ignore
    } finally {
      setActionLoading(false);
    }
  }

  const currentPlan = PLANS.find((p) => p.id === tier) || PLANS[0];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <CreditCard className="h-6 w-6 text-teal-600" />
          Subscription
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage your plan and billing
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      ) : (
        <>
          {/* Current plan card */}
          <div className="bg-gradient-to-r from-teal-600 to-emerald-600 rounded-xl p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-teal-100 text-sm">Current Plan</p>
                <h2 className="text-2xl font-bold mt-1">{currentPlan.name}</h2>
                <p className="text-teal-100 text-sm mt-1">
                  {currentPlan.price > 0
                    ? `$${currentPlan.price.toFixed(2)} / month`
                    : "Free forever"}
                </p>
              </div>
              <div className="text-right">
                {subscription?.current_period_end && (
                  <p className="text-sm text-teal-100">
                    {subscription.status === "active"
                      ? "Renews"
                      : "Expires"}{" "}
                    {new Date(
                      subscription.current_period_end,
                    ).toLocaleDateString()}
                  </p>
                )}
                <span
                  className={`inline-block mt-1 text-xs font-bold px-2 py-0.5 rounded-full ${
                    subscription?.status === "active"
                      ? "bg-white/20 text-white"
                      : "bg-yellow-400/20 text-yellow-200"
                  }`}
                >
                  {subscription?.status || "active"}
                </span>
              </div>
            </div>
          </div>

          {/* Plans comparison */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              All Plans
            </h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {PLANS.map((plan) => {
                const Icon = plan.icon;
                const isCurrent = plan.id === tier;
                const isUpgrade =
                  PLANS.indexOf(plan) >
                  PLANS.findIndex((p) => p.id === tier);

                return (
                  <div
                    key={plan.id}
                    className={`relative bg-white rounded-xl border-2 p-5 ${
                      isCurrent
                        ? "border-teal-500"
                        : plan.popular
                          ? "border-teal-200"
                          : "border-gray-200"
                    }`}
                  >
                    {plan.popular && !isCurrent && (
                      <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[10px] font-bold uppercase bg-teal-500 text-white px-2 py-0.5 rounded-full">
                        Popular
                      </span>
                    )}
                    {isCurrent && (
                      <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[10px] font-bold uppercase bg-teal-600 text-white px-2 py-0.5 rounded-full">
                        Current
                      </span>
                    )}

                    <Icon className="h-6 w-6 text-teal-600 mb-3" />
                    <h3 className="text-lg font-bold text-gray-900">
                      {plan.name}
                    </h3>
                    <p className="text-2xl font-bold text-gray-900 mt-1">
                      ${plan.price.toFixed(2)}
                      <span className="text-sm font-normal text-gray-500">
                        /mo
                      </span>
                    </p>

                    <ul className="mt-4 space-y-2">
                      {plan.features.map((f) => (
                        <li
                          key={f}
                          className="flex items-start gap-2 text-sm text-gray-600"
                        >
                          <Check className="h-4 w-4 text-teal-500 mt-0.5 flex-shrink-0" />
                          {f}
                        </li>
                      ))}
                    </ul>

                    <div className="mt-5">
                      {isCurrent ? (
                        <span className="block w-full text-center py-2 bg-gray-100 text-gray-500 rounded-lg text-sm font-medium cursor-default">
                          Current Plan
                        </span>
                      ) : isUpgrade ? (
                        <button
                          onClick={() => handleUpgrade(plan.id)}
                          disabled={actionLoading}
                          className="w-full flex items-center justify-center gap-1 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 transition-colors"
                        >
                          Upgrade
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleUpgrade(plan.id)}
                          disabled={actionLoading}
                          className="w-full py-2 border border-gray-200 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors"
                        >
                          Downgrade
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Payment history */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Payment History
            </h2>
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {payments.length === 0 ? (
                <div className="text-center py-12">
                  <CreditCard className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">No payment history</p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="text-left font-medium text-gray-500 px-4 py-3">
                        Date
                      </th>
                      <th className="text-left font-medium text-gray-500 px-4 py-3">
                        Amount
                      </th>
                      <th className="text-left font-medium text-gray-500 px-4 py-3">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {payments.map((p) => (
                      <tr key={p.payment_id}>
                        <td className="px-4 py-3 text-gray-700">
                          {new Date(p.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-gray-900 font-medium">
                          ${p.amount.toFixed(2)} {p.currency?.toUpperCase()}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                              p.status === "succeeded" || p.status === "paid"
                                ? "bg-green-100 text-green-700"
                                : p.status === "pending"
                                  ? "bg-yellow-100 text-yellow-700"
                                  : "bg-red-100 text-red-700"
                            }`}
                          >
                            {p.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Cancel subscription */}
          {tier !== "freemium" && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5" />
                <div>
                  <h3 className="font-semibold text-gray-900">
                    Cancel Subscription
                  </h3>
                  <p className="text-sm text-gray-500 mt-1">
                    You will lose access to premium features at the end of your
                    billing period.
                  </p>
                  <button
                    onClick={() => setShowCancelDialog(true)}
                    className="mt-3 px-4 py-2 border border-red-300 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
                  >
                    Cancel Subscription
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Cancel confirmation dialog */}
          {showCancelDialog && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
              <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900">
                    Cancel subscription?
                  </h3>
                  <button
                    onClick={() => setShowCancelDialog(false)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <p className="text-sm text-gray-600 mb-6">
                  Are you sure you want to cancel your{" "}
                  <strong>{currentPlan.name}</strong> subscription? You will be
                  downgraded to the Free plan at the end of your current billing
                  period.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowCancelDialog(false)}
                    className="flex-1 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Keep Subscription
                  </button>
                  <button
                    onClick={handleCancel}
                    disabled={actionLoading}
                    className="flex-1 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                  >
                    {actionLoading && (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                    Yes, Cancel
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
