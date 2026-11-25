import { expect } from "@playwright/test"
import { test } from "./fixtures"

test.describe("Error pages", () => {
  test("an unknown URL shows the 404 page", async ({ page }) => {
    const response = await page.goto("/coucou")
    expect(response?.status()).toBe(404)
    await expect(page.locator("[role=banner].fr-header")).toBeVisible()
  })
})
