"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Globe,
  Mail,
  Lock,
  Eye,
  EyeOff,
  User,
  Loader2,
  AlertCircle,
  Check,
  Crown,
  Zap,
  Building2,
  MailCheck,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const TIERS = [
  {
    id: "freemium",
    name: "Free",
    price: "$0",
    period: "forever",
    icon: User,
    features: [
      "5 articles per day",
      "Basic search",
      "Map view",
      "Community features",
    ],
    highlighted: false,
  },
  {
    id: "basic",
    name: "Basic",
    price: "$9.99",
    period: "/month",
    icon: Zap,
    features: [
      "50 articles per day",
      "Deep search",
      "Bookmarks & history",
      "Email digests",
    ],
    highlighted: false,
  },
  {
    id: "professional",
    name: "Professional",
    price: "$29.99",
    period: "/month",
    icon: Crown,
    features: [
      "Unlimited articles",
      "API access (1,000/day)",
      "Priority analysis",
      "Custom feeds",
    ],
    highlighted: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "$99.99",
    period: "/month",
    icon: Building2,
    features: [
      "Everything in Pro",
      "Team features",
      "Dedicated SLA",
      "Custom integrations",
    ],
    highlighted: false,
  },
];

export default function SignupPage() {
  const router = useRouter();
  const { register, isLoggedIn, loading: authLoading } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [selectedTier, setSelectedTier] = useState("freemium");
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verificationSent, setVerificationSent] = useState(false);

  useEffect(() => {
    if (!authLoading && isLoggedIn) {
      router.replace("/dashboard");
    }
  }, [authLoading, isLoggedIn, router]);

  function validate(): string | null {
    if (!fullName.trim()) return "Full name is required";
    if (!email.trim()) return "Email is required";
    if (password.length < 8)
      return "Password must be at least 8 characters";
    if (password !== confirmPassword) return "Passwords do not match";
    if (!agreedToTerms)
      return "You must agree to the Terms of Service";
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await register(email, password, fullName);
      if (result.requiresVerification) {
        setVerificationSent(true);
      } else if (selectedTier && selectedTier !== "freemium") {
        // Paid tier picked — route to subscription page to complete payment.
        // The selected tier is preserved as a query param; the subscription page
        // pre-selects it for the user.
        router.push(`/dashboard/subscription?tier=${encodeURIComponent(selectedTier)}`);
      } else {
        router.push("/dashboard");
      }
    } catch (err: any) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-600 via-teal-700 to-emerald-800">
        <Loader2 className="h-8 w-8 animate-spin text-white" />
      </div>
    );
  }

  // Verification sent state
  if (verificationSent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-600 via-teal-700 to-emerald-800 px-4 py-12">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-2xl p-8 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-teal-100 rounded-full mb-4">
              <MailCheck className="h-8 w-8 text-teal-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Check your email
            </h2>
            <p className="text-gray-600 mb-6">
              We sent a verification link to{" "}
              <span className="font-medium text-gray-900">{email}</span>.
              Please verify your email to continue.
            </p>
            <Link
              href="/login"
              className="inline-block px-6 py-2.5 bg-teal-600 text-white rounded-lg font-medium text-sm hover:bg-teal-700 transition-colors"
            >
              Go to Sign In
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-600 via-teal-700 to-emerald-800 px-4 py-12">
      <div className="max-w-4xl mx-auto">
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

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
            Create your account
          </h1>
          <p className="text-sm text-gray-500 text-center mb-8">
            Join thousands of climate-conscious professionals
          </p>

          {/* Error */}
          {error && (
            <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 max-w-md mx-auto">
              <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="grid md:grid-cols-2 gap-8">
              {/* Left column: Account details */}
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-gray-900 mb-1">
                  Account details
                </h2>

                <div>
                  <label
                    htmlFor="fullName"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Full name
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      id="fullName"
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Your full name"
                      required
                      className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="signupEmail"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Email address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      id="signupEmail"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                      className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="signupPassword"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      id="signupPassword"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      required
                      minLength={8}
                      className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="confirmPassword"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Confirm password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      id="confirmPassword"
                      type={showPassword ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter your password"
                      required
                      className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                    />
                  </div>
                  {confirmPassword && password !== confirmPassword && (
                    <p className="text-xs text-red-500 mt-1">
                      Passwords do not match
                    </p>
                  )}
                </div>
              </div>

              {/* Right column: Tier selection */}
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-3">
                  Choose a plan
                </h2>
                <div className="space-y-2">
                  {TIERS.map((tier) => {
                    const Icon = tier.icon;
                    const selected = selectedTier === tier.id;
                    return (
                      <button
                        key={tier.id}
                        type="button"
                        onClick={() => setSelectedTier(tier.id)}
                        className={`w-full text-left p-3 rounded-lg border-2 transition-all ${
                          selected
                            ? "border-teal-500 bg-teal-50"
                            : "border-gray-200 hover:border-gray-300"
                        } ${tier.highlighted && !selected ? "ring-1 ring-teal-200" : ""}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <Icon
                              className={`h-4 w-4 ${selected ? "text-teal-600" : "text-gray-400"}`}
                            />
                            <span className="font-semibold text-sm text-gray-900">
                              {tier.name}
                            </span>
                            {tier.highlighted && (
                              <span className="text-[10px] font-bold uppercase bg-teal-100 text-teal-700 px-1.5 py-0.5 rounded">
                                Popular
                              </span>
                            )}
                          </div>
                          <span className="text-sm font-bold text-gray-900">
                            {tier.price}
                            <span className="text-xs font-normal text-gray-500">
                              {tier.period}
                            </span>
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                          {tier.features.map((f) => (
                            <span
                              key={f}
                              className="text-xs text-gray-500 flex items-center gap-1"
                            >
                              <Check className="h-3 w-3 text-teal-500" />
                              {f}
                            </span>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Terms & submit */}
            <div className="mt-8 max-w-md mx-auto">
              <label className="flex items-start gap-2 mb-4 cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreedToTerms}
                  onChange={(e) => setAgreedToTerms(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                />
                <span className="text-sm text-gray-600">
                  I agree to the{" "}
                  <Link
                    href="/terms"
                    className="text-teal-600 hover:underline"
                  >
                    Terms of Service
                  </Link>{" "}
                  and{" "}
                  <Link
                    href="/privacy"
                    className="text-teal-600 hover:underline"
                  >
                    Privacy Policy
                  </Link>
                </span>
              </label>

              <button
                type="submit"
                disabled={loading || !agreedToTerms}
                className="w-full py-2.5 bg-teal-600 text-white rounded-lg font-medium text-sm hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                Create Account
              </button>

              <p className="mt-4 text-center text-sm text-gray-500">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="text-teal-600 font-semibold hover:text-teal-700"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
