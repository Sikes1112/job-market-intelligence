import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { FrontendAuthProvider } from "./auth";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <FrontendAuthProvider>
      <App />
    </FrontendAuthProvider>
  </StrictMode>,
);
