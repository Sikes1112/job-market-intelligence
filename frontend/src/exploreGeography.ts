import { resolveGeography } from "./api";
import {
  canonicalizeExploreState,
  type ExploreGeographicIdentity,
  type ExploreUrlState,
} from "./urlState";

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}

function identityResolves(
  token: string,
  state: ExploreUrlState,
  identities: ExploreGeographicIdentity[],
): boolean {
  return Boolean(canonicalizeExploreState({
    ...state,
    focus: token,
    selected: [],
    geographicScope: [],
  }, identities).focus);
}

/** Resolve every geographic URL token through the shared Layer 42A contract. */
export async function canonicalizeExploreGeography(
  state: ExploreUrlState,
  knownIdentities: ExploreGeographicIdentity[] = [],
): Promise<ExploreUrlState> {
  const unresolved = unique([
    ...(state.focus ? [state.focus] : []),
    ...state.selected,
    ...state.geographicScope,
  ]).filter((token) => !identityResolves(token, state, knownIdentities));

  const resolved = await Promise.all(unresolved.map(async (token) => {
    try {
      const identity = (await resolveGeography(token)).data;
      return identity
        ? {
            region_id: identity.region_id,
            public_slug: identity.public_slug,
            aliases: [token],
          }
        : null;
    } catch {
      return null;
    }
  }));

  return canonicalizeExploreState(
    state,
    [...knownIdentities, ...resolved.flatMap((identity) => identity ? [identity] : [])],
  );
}
