import { describe, expect, test } from "vitest";
import {
  isProductPage,
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
