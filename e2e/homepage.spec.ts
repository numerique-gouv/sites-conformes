import { expect } from "@playwright/test"
import { test } from "./fixtures"

test.describe("Page d’accueil", () => {
  // Tagged @regression: the fixtures hook captures a full-page screenshot after
  // this test and compares it against the baseline rendered from main. A visual
  // change to the homepage will fail the comparison job.
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
