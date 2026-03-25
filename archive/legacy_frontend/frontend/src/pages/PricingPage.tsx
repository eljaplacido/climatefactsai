import React from 'react';
import { Link } from 'react-router-dom';
import { Check, Crown } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const plans = [
  {
    name: 'Freemium',
    price: '€0',
    period: 'forever',
    tier: 'freemium',
    features: [
      '5 articles per day',
      '10 searches per day',
      'Basic filters',
      'Community support',
    ],
    limitations: [
      'No URL analysis',
      'No exports',
      'No API access',
      'Ads supported',
    ],
  },
  {
    name: 'Basic',
    price: '€9.99',
    period: 'per month',
    tier: 'basic',
    popular: false,
    features: [
      '50 articles per day',
      '50 searches per day',
      '5 URL analyses per month',
      'Saved searches',
      'Email notifications',
      'Email support',
      'No ads',
    ],
  },
  {
    name: 'Professional',
    price: '€29.99',
    period: 'per month',
    tier: 'professional',
    popular: true,
    features: [
      'Unlimited articles',
      'Unlimited searches',
      '20 URL analyses per month',
      'Semantic search',
      'PDF/CSV exports',
      'Up to 5 API keys',
      '1000 API calls per day',
      'Priority support',
      'No ads',
    ],
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    tier: 'enterprise',
    features: [
      'Everything in Professional',
      'Unlimited URL analyses',
      'Unlimited API keys',
      'Unlimited API calls',
      'Custom dashboards',
      'Dedicated support',
      'SLA guarantee',
      'Custom integrations',
    ],
  },
];

export const PricingPage: React.FC = () => {
  const { user, isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Choose Your Plan
          </h1>
          <p className="text-xl text-gray-600">
            Get started with CliLens.AI and unlock powerful fact-checking features
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {plans.map((plan) => (
            <div
              key={plan.tier}
              className={`bg-white rounded-lg shadow-xl overflow-hidden ${
                plan.popular ? 'ring-4 ring-blue-600 transform scale-105' : ''
              }`}
            >
              {plan.popular && (
                <div className="bg-blue-600 text-white text-center py-2 font-medium">
                  Most Popular
                </div>
              )}

              <div className="p-6">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">
                  {plan.name}
                </h3>
                <div className="mb-6">
                  <span className="text-4xl font-bold text-gray-900">
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className="text-gray-600 ml-2">{plan.period}</span>
                  )}
                </div>

                <ul className="space-y-3 mb-6">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start">
                      <Check className="w-5 h-5 text-green-600 mt-0.5 mr-3 flex-shrink-0" />
                      <span className="text-sm text-gray-700">{feature}</span>
                    </li>
                  ))}
                  {plan.limitations?.map((limitation, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="w-5 h-5 text-gray-400 mr-3 flex-shrink-0">
                        ✕
                      </span>
                      <span className="text-sm text-gray-500">{limitation}</span>
                    </li>
                  ))}
                </ul>

                {user?.subscription_tier === plan.tier ? (
                  <button
                    disabled
                    className="w-full bg-gray-200 text-gray-600 py-3 rounded-lg font-medium cursor-not-allowed"
                  >
                    Current Plan
                  </button>
                ) : plan.tier === 'freemium' ? (
                  <Link
                    to={isAuthenticated ? '/dashboard' : '/register'}
                    className="block w-full bg-gray-600 text-white py-3 rounded-lg font-medium text-center hover:bg-gray-700"
                  >
                    Get Started
                  </Link>
                ) : plan.tier === 'enterprise' ? (
                  <a
                    href="mailto:sales@clilens.ai"
                    className="block w-full bg-gray-900 text-white py-3 rounded-lg font-medium text-center hover:bg-gray-800"
                  >
                    Contact Sales
                  </a>
                ) : (
                  <Link
                    to={isAuthenticated ? `/checkout/${plan.tier}` : '/register'}
                    className={`block w-full py-3 rounded-lg font-medium text-center ${
                      plan.popular
                        ? 'bg-blue-600 text-white hover:bg-blue-700'
                        : 'bg-gray-900 text-white hover:bg-gray-800'
                    }`}
                  >
                    {isAuthenticated ? 'Upgrade Now' : 'Start Free Trial'}
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* FAQ Section */}
        <div className="mt-16 bg-white rounded-lg shadow-xl p-8">
          <h2 className="text-2xl font-bold mb-6 text-center">
            Frequently Asked Questions
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold mb-2">Can I change plans later?</h3>
              <p className="text-gray-600 text-sm">
                Yes, you can upgrade or downgrade at any time. Changes take effect immediately.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">What payment methods do you accept?</h3>
              <p className="text-gray-600 text-sm">
                We accept all major credit cards through Stripe.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Is there a free trial?</h3>
              <p className="text-gray-600 text-sm">
                The Freemium plan is always free. Premium plans offer 14-day money-back guarantee.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Can I cancel anytime?</h3>
              <p className="text-gray-600 text-sm">
                Yes, you can cancel your subscription at any time with no penalties.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
