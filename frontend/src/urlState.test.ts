import { describe, expect, test } from "vitest";
import {
  isProductPage,
  marketIntelligenceUrl,
  parseRoute,
  userIntelligenceDashboardUrl,
} from "./urlState";

describe("urlState dashboard route", () => {
  test("parses the user intelligence dashboard product route", () => {
    const route = parseRoute("/markets/dashboard", "");

    expect(route.page).toBe("dashboard");
    expect(isProductPage(route.page)).toBe(true);
    expect(userIntelligenceDashboardUrl()).toBe("/markets/dashboard");
  });
});

describe("urlState market intelligence route", () => {
  test("parses and serializes the market intelligence product route", () => {
    const route = parseRoute(
      "/markets/intelligence",
      "?goal=data_science&market=atlanta&compare_a=atlanta&compare_b=boston",
    );

    expect(route.page).toBe("intelligence");
    expect(isProductPage(route.page)).toBe(true);
    expect(route.intelligence).toEqual({
      goal: "data_science",
      marketKey: "atlanta",
      compareA: "atlanta",
      compareB: "boston",
    });
    expect(marketIntelligenceUrl(route.intelligence)).toBe(
      "/markets/intelligence?goal=data_science&market=atlanta&compare_a=atlanta&compare_b=boston",
    );
  });
});
