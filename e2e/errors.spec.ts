import { expect } from "@playwright/test"
import { test } from "./fixtures"

test.describe("Pages d'erreur", () => {
  test("une URL inconnue affiche la page 404", async ({ page }) => {
    const response = await page.goto("/coucou")
    expect(response?.status()).toBe(404)
    await expect(page.locator("[role=banner].fr-header")).toBeVisible()
  })
})
