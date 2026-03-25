"use client";
import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };
  static getDerivedStateFromError(error: Error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div role="alert" className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center p-8 max-w-md">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Something went wrong</h1>
            <p className="text-gray-600 mb-6">{this.state.error?.message || "An unexpected error occurred."}</p>
            <button onClick={() => this.setState({ hasError: false, error: null })} className="px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700">Try again</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
