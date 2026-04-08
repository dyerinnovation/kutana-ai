import { Component, type ReactNode } from "react";
import { KutanaKMark } from "@/components/Logo";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = "/";
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 px-6 text-center">
        <KutanaKMark size={48} />
        <h1 className="mt-6 text-2xl font-bold text-gray-50">
          Something went wrong
        </h1>
        <p className="mt-2 max-w-md text-sm text-gray-400">
          An unexpected error occurred. Please try again or return to the
          dashboard.
        </p>
        {this.state.error && (
          <pre className="mt-4 max-w-lg overflow-auto rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-left text-xs text-gray-500">
            {this.state.error.message}
          </pre>
        )}
        <button
          onClick={this.handleReset}
          className="mt-6 inline-flex items-center rounded-lg bg-green-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-green-500"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }
}
