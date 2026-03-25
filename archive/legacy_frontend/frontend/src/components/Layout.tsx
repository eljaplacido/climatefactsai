import { Link, useLocation } from "react-router-dom";
import { Globe, Home, Settings, Info, LogIn, UserPlus, LayoutDashboard, LogOut, Crown } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

interface LayoutProps {
  children: React.ReactNode;
}

function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { isAuthenticated, user, logout } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="flex items-center space-x-2 group">
              <div className="bg-gradient-to-br from-green-500 to-blue-500 p-2 rounded-lg group-hover:scale-105 transition-transform">
                <Globe className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">CliLens.AI</h1>
                <p className="text-xs text-gray-500">Trusted climate intelligence</p>
              </div>
            </Link>

            <nav className="flex items-center space-x-1">
              <Link
                to="/"
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/")
                    ? "bg-green-50 text-green-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Home className="h-5 w-5" />
                <span className="font-medium">Home</span>
              </Link>

              <Link
                to="/pricing"
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/pricing")
                    ? "bg-green-50 text-green-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Crown className="h-5 w-5" />
                <span className="font-medium">Pricing</span>
              </Link>

              <Link
                to="/about"
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/about")
                    ? "bg-green-50 text-green-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Info className="h-5 w-5" />
                <span className="font-medium">About</span>
              </Link>

              {isAuthenticated ? (
                <>
                  <Link
                    to="/dashboard"
                    className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                      isActive("/dashboard")
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    <LayoutDashboard className="h-5 w-5" />
                    <span className="font-medium">Dashboard</span>
                  </Link>

                  <button
                    onClick={logout}
                    className="flex items-center space-x-2 px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <LogOut className="h-5 w-5" />
                    <span className="font-medium">Logout</span>
                  </button>

                  <div className="ml-2 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                    {user?.subscription_tier}
                  </div>
                </>
              ) : (
                <>
                  <Link
                    to="/login"
                    className="flex items-center space-x-2 px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <LogIn className="h-5 w-5" />
                    <span className="font-medium">Login</span>
                  </Link>

                  <Link
                    to="/register"
                    className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                  >
                    <UserPlus className="h-5 w-5" />
                    <span className="font-medium">Sign Up</span>
                  </Link>
                </>
              )}
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Climate News</h3>
              <p className="text-sm text-gray-600">
                Independent climate intelligence with transparent fact-checking, powered by a multi-agent news pipeline.
              </p>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Learn more</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>
                  <Link to="/about" className="hover:text-climate-green-600">How it works</Link>
                </li>
                <li>
                  <a href="#" className="hover:text-climate-green-600">Source catalogue</a>
                </li>
                <li>
                  <a href="#" className="hover:text-climate-green-600">Contact</a>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Technology</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>Multi-agent automation</li>
                <li>ClimateCheck, NOAA, NASA data</li>
                <li>Claude 3.5 Sonnet</li>
                <li>Open source tooling</li>
              </ul>
            </div>
          </div>

          <div className="mt-8 pt-8 border-t border-gray-200 text-center text-sm text-gray-500">
            <p>&copy; {new Date().getFullYear()} Climate News. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default Layout;
