import type { ErrorInfo, ReactNode } from 'react';
import { Component } from 'react';
import { useLocation } from 'react-router-dom';

const isDevelopment = import.meta.env.DEV;

export interface ErrorBoundaryFallbackProps {
  error: Error | null;
  reset: () => void;
  reload: () => void;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (props: ErrorBoundaryFallbackProps) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

function normalizeError(error: unknown): Error {
  if (error instanceof Error) {
    return error;
  }

  if (typeof error === 'string') {
    return new Error(error);
  }

  return new Error('An unknown UI error occurred.');
}

function reportError(error: Error, errorInfo: ErrorInfo): void {
  if (isDevelopment) {
    console.error('Unhandled UI error', error, errorInfo);
  }

  // TODO: Forward errors to a tracking service when one is configured.
}

function DefaultFallback({ error, reload }: ErrorBoundaryFallbackProps) {
  return (
    <main className="error-boundary error-boundary--page" role="alert" aria-live="assertive">
      <span className="error-boundary__eyebrow">Unexpected app error</span>
      <h1 className="error-boundary__title">Aithena ran into a problem.</h1>
      <p className="error-boundary__message">
        Try reloading the page to restore search, uploads, and navigation.
      </p>
      <div className="error-boundary__actions">
        <button type="button" className="error-boundary__button" onClick={reload}>
          Reload Aithena
        </button>
      </div>
      {isDevelopment && error && (
        <details className="error-boundary__details">
          <summary>Technical details</summary>
          <pre className="error-boundary__stack">{error.stack ?? error.message}</pre>
        </details>
      )}
    </main>
  );
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    return {
      hasError: true,
      error: normalizeError(error),
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    reportError(error, errorInfo);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  reload = () => {
    this.reset();
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const fallbackProps: ErrorBoundaryFallbackProps = {
      error: this.state.error,
      reset: this.reset,
      reload: this.reload,
    };

    return this.props.fallback ? (
      this.props.fallback(fallbackProps)
    ) : (
      <DefaultFallback {...fallbackProps} />
    );
  }
}

export function RouteErrorBoundary({ children, fallback }: ErrorBoundaryProps) {
  const location = useLocation();
  const routeKey = location.key || `${location.pathname}${location.search}${location.hash}`;

  return (
    <ErrorBoundary key={routeKey} fallback={fallback}>
      {children}
    </ErrorBoundary>
  );
}

export default ErrorBoundary;
