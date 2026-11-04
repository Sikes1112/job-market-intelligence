import { expect, test } from "vitest";
import { opportunityRole, OPPORTUNITY_ROLE_OPTIONS } from "./opportunityContext";
test("verified aliases use only real categories and unknowns stay unmapped", () => {
  for (const [alias, category] of [["Data Science", "data_ai"],["ai_ml","applied_ai"],["software_engineer","software_engineering"],["technical_product","product_management"],["solutions_engineer","solutions_engineering"]]) {
    expect(opportunityRole(alias)).toBe(category);
    expect(OPPORTUNITY_ROLE_OPTIONS.map(([value])=>value)).toContain(category);
  }
  expect(opportunityRole("marine ecologist")).toBeUndefined();
});
