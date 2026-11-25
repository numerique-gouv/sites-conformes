import { expect } from "@playwright/test"
import { test } from "./fixtures"

// The @regression tag makes the fixtures hook capture a full-page screenshot
// and compare it against the baseline rendered from main.
test.describe("Home page", () => {
  test(
    "the home page renders without errors",
    { tag: "@regression" },
    async ({ page }) => {
      const response = await page.goto("/")
      expect(response?.status()).toBe(200)
      await expect(page.locator("body")).toBeVisible()
    },
  )
})
