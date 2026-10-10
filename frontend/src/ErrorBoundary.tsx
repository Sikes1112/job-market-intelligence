import { Component, type ReactNode } from "react";
import { reportFrontendError } from "./errorMonitoring";
import { runtimeConfig } from "./runtimeConfig";

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
            <p className="eyebrow">Beta · release {runtimeConfig.releaseId}</p>
            <h1>This page temporarily failed</h1>
            <p>
              Your saved work is still on the server. Reload this page or return to Explore.
            </p>
            <a className="primary-link" href="/markets">Return to Explore</a>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
