import { getOpportunityRoutes } from "./api";
import type {
  OpportunityLocationMode,
  OpportunityProgramType,
  OpportunityRouteRequest,
} from "./opportunityTypes";

export const DEFAULT_ROUTE_REGIONS = ["greater_boston", "atlanta"];
export const DEFAULT_ROUTE_ROLE_FAMILIES = ["software_engineering", "product_management"];

export const PROGRAM_TYPE_OPTIONS: OpportunityProgramType[] = [
  "internship",
  "new_grad_role",
  "rotational_program",
  "apprenticeship",
];

export const LOCATION_MODE_OPTIONS: OpportunityLocationMode[] = [
  "hybrid",
  "remote",
  "onsite",
  "mixed",
];

export const DEFAULT_OPPORTUNITY_ROUTE_REQUEST: OpportunityRouteRequest = {
  user_intent_summary: "Early-career candidate looking for practical software routes.",
  target_regions: DEFAULT_ROUTE_REGIONS,
  target_role_families: DEFAULT_ROUTE_ROLE_FAMILIES,
  preferred_program_types: ["internship", "new_grad_role"],
  preferred_location_modes: ["hybrid", "remote"],
  experience_level: "internship",
  skills: ["python", "data", "cloud"],
  background_tags: ["computer_science"],
  constraints: ["needs verified or source-checked sources"],
  include_unverified: false,
  limit: 5,
};

export function commaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function toggleValue<T extends string>(values: T[], value: T): T[] {
  return values.includes(value)
    ? values.filter((current) => current !== value)
    : [...values, value];
}

export function requestOpportunityRoutes(body: OpportunityRouteRequest) {
  return getOpportunityRoutes(body);
}
