import { expect } from "@playwright/test"
import { test } from "./fixtures"

// Demo pages created by `create_demo_pages`. Not tagged @regression: their
// text comes from an unseeded Faker, so screenshots differ on every run.
const pages = [
  "/menu_page/common_blocks/",
  "/menu_page/hero_blocks/hero-text-image/",
  "/menu_page/hero_blocks/hero-text-wide-image/",
]

test.describe("Images", () => {
  for (const url of pages) {
    test(`Les images de ${url} ont un texte alternatif`, async ({ page }) => {
      const response = await page.goto(url)
      expect(response?.status()).toBe(200)

      const images = page.locator("main img")
      expect(await images.count()).toBeGreaterThan(0)
      for (const image of await images.all()) {
        await expect(image).toHaveAttribute("alt")
      }
    })
  }

  test("Les images matricielles passent par la balise picture en WebP", async ({
    page,
  }) => {
    await page.goto("/menu_page/hero_blocks/hero-text-image/")

    const image = page.locator('picture img[src$=".webp"]').first()
    await expect(image).toHaveAttribute("alt")
  })
})
