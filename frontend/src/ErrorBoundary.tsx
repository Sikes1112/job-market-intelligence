import { Component, type ReactNode } from "react";
import { reportFrontendError } from "./errorMonitoring";

type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  failed: boolean;
};

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error): void {
    reportFrontendError(error, {
      source: "error_boundary",
      route: `${window.location.pathname}${window.location.search}`,
    });
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="fatal-error-shell" role="alert">
          <section className="fatal-error-panel">
            <p className="eyebrow">Public demo error</p>
            <h1>Demo temporarily unavailable</h1>
            <p>
              The demo failed safely while rendering this page. Refresh the page or try the
              markets demo entry again.
            </p>
            <a className="primary-link" href="/markets">Open demo</a>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
