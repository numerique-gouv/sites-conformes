import { expect } from "@playwright/test"
import { test } from "./fixtures"

test.describe("Menus", () => {
  test("Les sous-menus fonctionnent", async ({ page }) => {
    const response = await page.goto("/")
    // TODO: réparer
    expect(response?.status()).not.toBe(200)

    await page.goto("/menu_page/form_with_all_fields/")
    const menuPrincipal = page.locator("[aria-label='Menu principal']")
    await expect(menuPrincipal).toBeVisible()
    const bouton = menuPrincipal.getByText("Pages d’exemple")
    const lien = menuPrincipal.getByText("Formulaire avec tous les champs")
    await expect(lien).not.toBeVisible()
    await bouton.click()
    await expect(lien).toBeVisible()
  })
})
