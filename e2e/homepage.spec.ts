import { expect } from "@playwright/test"
import { test } from "./fixtures"

// Placeholder smoke test so the e2e pipeline is green and exercises the full
// baseline -> compare visual-regression flow end-to-end. Replace/expand with
// real scenarios. The @regression tag makes the fixtures hook capture a
// full-page screenshot and compare it against the baseline rendered from main.
test.describe("Page d’accueil", () => {
  test(
    "L’accueil s’affiche sans erreur",
    { tag: "@regression" },
    async ({ page }) => {
      const response = await page.goto("/")
      expect(response?.status()).toBe(200)
      await expect(page.locator("body")).toBeVisible()
    },
  )
})
