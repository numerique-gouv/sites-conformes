import { expect, type Page } from "@playwright/test"
import { test } from "./fixtures"

// Walks through the data of `create_demo_pages --slug categories`.

const QUIMPER = "Protéger un chantier à Quimper"
const VANNES = "Aménager les horaires à Vannes"
const RENNES = "Prévenir les coups de chaleur à Rennes"
const STRASBOURG = "Accueillir les patients à Strasbourg"
const EQUIPEMENTS = "Choisir ses équipements de chantier"

const chip = (page: Page, name: string) =>
  page.locator("#category-filter-form label.fr-tag", { hasText: name })

// Sorted, so that the assertions don't depend on the listing order.
const expectGuides = async (page: Page, titles: string[]) => {
  const cards = page.locator(".fr-card__title")
  await expect(cards).toHaveCount(titles.length)
  expect((await cards.allTextContents()).map((t) => t.trim()).sort()).toEqual(
    [...titles].sort(),
  )
}

test.describe("Filtres par catégorie du catalogue", () => {
  test("Cocher une région montre ses pages, puis une sous-catégorie affine", async ({
    page,
  }) => {
    await page.goto("/guides/")
    await expectGuides(page, [QUIMPER, VANNES, RENNES, STRASBOURG, EQUIPEMENTS])
    await expect(chip(page, "Finistère")).toHaveCount(0)

    await chip(page, "Bretagne").click()
    await expect(page).toHaveURL(/category=bretagne/)
    await expectGuides(page, [QUIMPER, VANNES, RENNES])
    await expect(chip(page, "Bretagne")).toHaveAttribute("aria-pressed", "true")

    await chip(page, "Finistère").click()
    await expect(page).toHaveURL(/category=finistere/)
    await expectGuides(page, [QUIMPER])
  })

  test("Décocher une région décoche aussi ses sous-catégories", async ({
    page,
  }) => {
    await page.goto("/guides/?category=bretagne&category=finistere")
    await expectGuides(page, [QUIMPER])

    await chip(page, "Bretagne").click()

    await expect(page).not.toHaveURL(/category=/)
    await expectGuides(page, [QUIMPER, VANNES, RENNES, STRASBOURG, EQUIPEMENTS])
    await expect(chip(page, "Finistère")).toHaveCount(0)
  })

  test("Les catégories de plusieurs groupes se cumulent", async ({ page }) => {
    await page.goto("/guides/")

    await chip(page, "Alsace").click()
    await expectGuides(page, [STRASBOURG])

    await chip(page, "BTP").click()
    await expect(page).toHaveURL(/category=alsace/)
    await expect(page).toHaveURL(/category=btp/)
    await expectGuides(page, [STRASBOURG, QUIMPER, VANNES, EQUIPEMENTS])
  })
})

test.describe("Catégories du blog", () => {
  test("Le lien de catégorie d’un article filtre l’index", async ({ page }) => {
    await page.goto("/actualités/plan-canicule-bretagne/")

    await page.getByRole("link", { name: "Bretagne", exact: true }).click()

    await expect(page).toHaveURL(/category=bretagne/)
    await expect(page.locator("a.fr-tag", { hasText: "Bretagne" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    await expect(page.locator(".fr-card__title")).toHaveText([
      "Un plan canicule pour la Bretagne",
    ])
  })
})
