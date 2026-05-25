import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AppErrorBoundary } from "./ErrorBoundary";
import { FrontendAuthProvider } from "./auth";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppErrorBoundary>
      <FrontendAuthProvider>
        <App />
      </FrontendAuthProvider>
    </AppErrorBoundary>
  </StrictMode>,
);
