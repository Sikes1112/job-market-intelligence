/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Auth0Provider,
  useAuth0,
  type AppState,
  type User as Auth0User,
} from "@auth0/auth0-react";
import { runtimeConfig } from "./runtimeConfig";
import {
  initializeGuestSession,
  subscribeGuestSession,
  type GuestSessionEvent,
} from "./guestSession";

type FrontendAuthConfig = {
  domain: string;
  clientId: string;
  audience?: string;
  redirectUri: string;
};

export type FrontendAuthUser = Pick<
  Auth0User,
  "email" | "email_verified" | "name" | "nickname" | "picture" | "sub"
>;

export type FrontendAuthContextValue = {
  isConfigured: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: Error | null;
  user: FrontendAuthUser | null;
  login: () => Promise<void>;
  logout: () => void;
  getAccessTokenSilently: () => Promise<string | null>;
  sessionMessage?: string | null;
  retrySession?: () => Promise<void>;
};

const authConfig = readAuthConfig();
const localAuthEnabled = import.meta.env.DEV && import.meta.env.VITE_LOCAL_AUTH === "true";

async function openUnavailableAuthNotice() {
  if (localAuthEnabled) return;
  window.history.pushState({}, document.title, "/markets/account");
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const missingAuthValue: FrontendAuthContextValue = {
  isConfigured: localAuthEnabled,
  isAuthenticated: localAuthEnabled,
  isLoading: false,
  error: null,
  user: localAuthEnabled ? { sub: "local|explorer", name: "Local explorer" } : null,
  login: openUnavailableAuthNotice,
  logout: () => undefined,
  getAccessTokenSilently: async () => null,
};

const FrontendAuthContext = createContext<FrontendAuthContextValue>(missingAuthValue);

function readAuthConfig(): FrontendAuthConfig | null {
  const domain = runtimeConfig.auth0Domain;
  const clientId = runtimeConfig.auth0ClientId;
  const audience = runtimeConfig.auth0Audience;
  if (!domain || !clientId) return null;

  const redirectUri =
    import.meta.env.VITE_AUTH0_REDIRECT_URI?.trim()
    || `${window.location.origin}/markets`;

  return {
    domain,
    clientId,
    audience: audience || undefined,
    redirectUri,
  };
}

function redirectAfterAuth(appState?: AppState) {
  const returnTo = typeof appState?.returnTo === "string" ? appState.returnTo : "/markets";
  window.history.replaceState({}, document.title, returnTo);
}

function Auth0ContextBridge({ children }: { children: ReactNode }) {
  const auth0 = useAuth0();

  const login = useCallback(async () => {
    await auth0.loginWithRedirect({
      appState: { returnTo: `${window.location.pathname}${window.location.search}` },
      authorizationParams: {
        audience: authConfig?.audience,
      },
    });
  }, [auth0]);

  const logout = useCallback(() => {
    auth0.logout({
      logoutParams: {
        returnTo: window.location.origin,
      },
    });
  }, [auth0]);

  const getToken = useCallback(async () => {
    if (!auth0.isAuthenticated) return null;
    return auth0.getAccessTokenSilently({
      authorizationParams: {
        audience: authConfig?.audience,
      },
    });
  }, [auth0]);

  const value: FrontendAuthContextValue = {
    isConfigured: true,
    isAuthenticated: auth0.isAuthenticated,
    isLoading: auth0.isLoading,
    error: auth0.error ?? null,
    user: auth0.user ?? null,
    login,
    logout,
    getAccessTokenSilently: getToken,
  };

  return (
    <FrontendAuthContext.Provider value={value}>
      {children}
    </FrontendAuthContext.Provider>
  );
}

function PublicGuestContextBridge({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);

  const start = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await initializeGuestSession();
      setIsAuthenticated(true);
    } catch (reason) {
      setIsAuthenticated(false);
      setError(reason instanceof Error ? reason : new Error("The live demo could not start."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const handleEvent = (event: GuestSessionEvent) => {
      if (event.state === "unavailable") {
        setError(new Error(event.message ?? "The live demo is temporarily unavailable."));
        setIsAuthenticated(false);
      } else {
        setError(null);
        setIsAuthenticated(true);
        if (event.state === "reset") setSessionMessage(event.message ?? null);
      }
      setIsLoading(false);
    };
    const unsubscribe = subscribeGuestSession(handleEvent);
    void start();
    return unsubscribe;
  }, [start]);

  const value = useMemo<FrontendAuthContextValue>(() => ({
    isConfigured: true,
    isAuthenticated,
    isLoading,
    error,
    user: isAuthenticated ? { sub: "public_guest", name: "Guest workspace" } : null,
    login: start,
    logout: () => undefined,
    getAccessTokenSilently: async () => null,
    sessionMessage,
    retrySession: start,
  }), [error, isAuthenticated, isLoading, sessionMessage, start]);

  return <FrontendAuthContext.Provider value={value}>{children}</FrontendAuthContext.Provider>;
}

export function FrontendAuthProvider({ children }: { children: ReactNode }) {
  if (runtimeConfig.isPublicGuestDemo) {
    return <PublicGuestContextBridge>{children}</PublicGuestContextBridge>;
  }
  if (!authConfig) {
    return (
      <FrontendAuthContext.Provider value={missingAuthValue}>
        {children}
      </FrontendAuthContext.Provider>
    );
  }

  return (
    <Auth0Provider
      cacheLocation="memory"
      clientId={authConfig.clientId}
      domain={authConfig.domain}
      onRedirectCallback={redirectAfterAuth}
      useRefreshTokens={false}
      authorizationParams={{
        audience: authConfig.audience,
        redirect_uri: authConfig.redirectUri,
      }}
    >
      <Auth0ContextBridge>{children}</Auth0ContextBridge>
    </Auth0Provider>
  );
}

export function useFrontendAuth(): FrontendAuthContextValue {
  return useContext(FrontendAuthContext);
}
