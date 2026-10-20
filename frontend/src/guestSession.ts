import { runtimeConfig } from "./runtimeConfig";

const CHANNEL_NAME = "jmi-public-guest-session";
const PEER_WAIT_MS = 120;
const BOOTSTRAP_TIMEOUT_MS = 75_000;

type GuestSessionBootstrap = {
  status: "active";
  csrf_token: string;
  expires_at: string;
  created: boolean;
  replaced: boolean;
};

type GuestSessionState = {
  csrfToken: string;
  expiresAt: string;
};

type GuestSessionMessage =
  | { type: "token-request"; sender: string }
  | { type: "token-update"; sender: string; csrfToken: string; expiresAt: string };

export type GuestSessionEvent = {
  state: "ready" | "reset" | "unavailable";
  message?: string;
};

const tabId = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
let sessionState: GuestSessionState | null = null;
let bootstrapPromise: Promise<GuestSessionBootstrap> | null = null;
let recoveryPromise: Promise<GuestSessionBootstrap> | null = null;
let channel: BroadcastChannel | null = null;
const listeners = new Set<(event: GuestSessionEvent) => void>();

function notify(event: GuestSessionEvent): void {
  for (const listener of listeners) listener(event);
}

function receiveState(csrfToken: string, expiresAt: string): void {
  if (!csrfToken || !expiresAt) return;
  sessionState = { csrfToken, expiresAt };
}

function sessionChannel(): BroadcastChannel | null {
  if (!runtimeConfig.isPublicGuestDemo || typeof BroadcastChannel === "undefined") return null;
  if (channel) return channel;
  channel = new BroadcastChannel(CHANNEL_NAME);
  channel.addEventListener("message", (event: MessageEvent<GuestSessionMessage>) => {
    const message = event.data;
    if (!message || message.sender === tabId) return;
    if (message.type === "token-request" && sessionState) {
      channel?.postMessage({
        type: "token-update",
        sender: tabId,
        csrfToken: sessionState.csrfToken,
        expiresAt: sessionState.expiresAt,
      } satisfies GuestSessionMessage);
      return;
    }
    if (message.type === "token-update") {
      receiveState(message.csrfToken, message.expiresAt);
      notify({ state: "ready" });
    }
  });
  return channel;
}

function broadcastState(state: GuestSessionState): void {
  sessionChannel()?.postMessage({
    type: "token-update",
    sender: tabId,
    csrfToken: state.csrfToken,
    expiresAt: state.expiresAt,
  } satisfies GuestSessionMessage);
}

async function requestPeerState(previousToken?: string): Promise<GuestSessionState | null> {
  const activeChannel = sessionChannel();
  if (!activeChannel) return null;
  const startingToken = sessionState?.csrfToken;
  activeChannel.postMessage({ type: "token-request", sender: tabId } satisfies GuestSessionMessage);
  await new Promise((resolve) => globalThis.setTimeout(resolve, PEER_WAIT_MS));
  if (!sessionState) return null;
  if (previousToken && sessionState.csrfToken === previousToken) return null;
  if (!previousToken && startingToken && sessionState.csrfToken === startingToken) return sessionState;
  return sessionState;
}

async function fetchBootstrap(): Promise<GuestSessionBootstrap> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), BOOTSTRAP_TIMEOUT_MS);
  try {
    const response = await fetch("/guest/session", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });
    const body = await response.json() as { data?: GuestSessionBootstrap; error?: { message?: string } };
    if (!response.ok || !body.data?.csrf_token || !body.data.expires_at) {
      throw new Error(body.error?.message ?? "The live demo could not start.");
    }
    const state = { csrfToken: body.data.csrf_token, expiresAt: body.data.expires_at };
    receiveState(state.csrfToken, state.expiresAt);
    broadcastState(state);
    return body.data;
  } catch (error) {
    const message = error instanceof DOMException && error.name === "AbortError"
      ? "The live demo is taking longer than expected to start."
      : error instanceof Error
        ? error.message
        : "The live demo could not start.";
    notify({ state: "unavailable", message });
    throw new Error(message, { cause: error });
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

async function withBootstrapLock<T>(operation: () => Promise<T>): Promise<T> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (!locks) return operation();
  return locks.request(CHANNEL_NAME, operation);
}

export async function initializeGuestSession(): Promise<GuestSessionBootstrap | null> {
  if (!runtimeConfig.isPublicGuestDemo) return null;
  if (sessionState) {
    return {
      status: "active",
      csrf_token: sessionState.csrfToken,
      expires_at: sessionState.expiresAt,
      created: false,
      replaced: false,
    };
  }
  if (bootstrapPromise) return bootstrapPromise;
  bootstrapPromise = withBootstrapLock(async () => {
    const peer = await requestPeerState();
    if (peer) {
      return {
        status: "active",
        csrf_token: peer.csrfToken,
        expires_at: peer.expiresAt,
        created: false,
        replaced: false,
      } satisfies GuestSessionBootstrap;
    }
    return fetchBootstrap();
  }).then((bootstrap) => {
    notify(bootstrap.replaced
      ? { state: "reset", message: "Your temporary workspace reset. A new session is ready." }
      : { state: "ready" });
    return bootstrap;
  }).finally(() => {
    bootstrapPromise = null;
  });
  return bootstrapPromise;
}

export async function recoverGuestSession(
  reason: "csrf" | "session",
): Promise<GuestSessionBootstrap> {
  if (!runtimeConfig.isPublicGuestDemo) throw new Error("Guest recovery is unavailable.");
  if (recoveryPromise) return recoveryPromise;
  const previousToken = sessionState?.csrfToken;
  recoveryPromise = withBootstrapLock(async () => {
    if (reason === "csrf") {
      const peer = await requestPeerState(previousToken);
      if (peer) {
        return {
          status: "active",
          csrf_token: peer.csrfToken,
          expires_at: peer.expiresAt,
          created: false,
          replaced: false,
        } satisfies GuestSessionBootstrap;
      }
    }
    sessionState = null;
    return fetchBootstrap();
  }).then((bootstrap) => {
    notify(bootstrap.created
      ? { state: "reset", message: "Your temporary workspace reset. A new session is ready." }
      : { state: "ready" });
    return bootstrap;
  }).finally(() => {
    recoveryPromise = null;
  });
  return recoveryPromise;
}

export function guestCsrfToken(): string | null {
  return sessionState?.csrfToken ?? null;
}

export function subscribeGuestSession(listener: (event: GuestSessionEvent) => void): () => void {
  listeners.add(listener);
  sessionChannel();
  return () => listeners.delete(listener);
}

export function resetGuestSessionMemoryForTests(): void {
  sessionState = null;
  bootstrapPromise = null;
  recoveryPromise = null;
  channel?.close();
  channel = null;
  listeners.clear();
}
