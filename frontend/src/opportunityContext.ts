/** Existing verified aliases shared by contextual opportunity links. */
export const OPPORTUNITY_ROLE_OPTIONS = [
  ["software_engineering", "Software engineering"],
  ["applied_ai", "Applied AI"],
  ["data_ai", "Data and AI"],
  ["product_management", "Technical product management"],
  ["solutions_engineering", "Solutions engineering"],
] as const;
const ROLE_MAPPINGS = new Map<string, string>([
  ["applied_ai", "applied_ai"], ["applied_ai_engineer", "applied_ai"], ["ai_ml", "applied_ai"],
  ["data_ai", "data_ai"], ["data_science", "data_ai"], ["product", "product_management"],
  ["product_management", "product_management"], ["technical_product", "product_management"],
  ["solutions_engineer", "solutions_engineering"], ["solutions_engineering", "solutions_engineering"],
  ["software_engineer", "software_engineering"], ["software_engineering", "software_engineering"],
]);
export function opportunityRole(value: string | null | undefined): string | undefined {
  return value ? ROLE_MAPPINGS.get(value.trim().toLocaleLowerCase().replaceAll(" ", "_")) : undefined;
}
