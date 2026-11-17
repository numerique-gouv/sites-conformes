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

test.describe("Administration des catégories", () => {
  const categories = "/cms-admin/snippets/sites_conformes_core/category/"

  test.beforeEach(async ({ page }) => {
    await page.goto("/cms-admin/login/")
    await page.locator("#id_username").fill(process.env.DJANGO_SUPERUSER_USERNAME!)
    await page.locator("#id_password").fill(process.env.DJANGO_SUPERUSER_PASSWORD!)
    await page.locator("#id_password").press("Enter")
    await expect(page).toHaveURL(/cms-admin\/$/)
  })

  test("La liste parcourt l’arborescence", async ({ page }) => {
    const names = page.locator("table tbody").getByRole("link")

    await page.goto(categories)
    await expect(names).toHaveText(["Régions", "Secteurs"])

    await page.getByRole("link", { name: "Régions", exact: true }).click()
    await expect(names).toHaveText(["Bretagne", "Finistère", "Morbihan", "Alsace"])

    const finistere = names.filter({ hasText: "Finistère" })
    await expect(finistere).toBeVisible()
    await page.getByRole("button", { name: "Sous-éléments de Bretagne" }).click()
    await expect(finistere).toBeHidden()
  })

  test("Une catégorie créée puis choisie sur une page filtre le catalogue", async ({
    page,
  }) => {
    const name = `Bas-Rhin ${Date.now()}`

    // networkidle: the slug is filled in by JavaScript, once the page is hydrated
    await page.goto(`${categories}add/`, { waitUntil: "networkidle" })
    await page.getByRole("textbox", { name: "Nom de la catégorie" }).pressSequentially(name)
    await expect(page.getByRole("textbox", { name: "Slug" })).toHaveValue(/^bas-rhin-\d+$/)
    await page.getByRole("combobox", { name: "Relative à" }).selectOption("Alsace")
    await page.getByRole("button", { name: "Enregistrer" }).click()
    await expect(page.locator(".messages .success")).toBeVisible()

    await page.goto("/guides/patients-strasbourg/")
    await page.locator("wagtail-userbar").getByRole("button").first().click()
    await page.getByRole("menuitem", { name: "Modifier cette page" }).click()
    await expect(page.getByRole("checkbox", { name })).toBeHidden()
    await page.getByRole("button", { name: "Sous-éléments de Alsace" }).click()
    await page.getByRole("checkbox", { name }).check()
    await page.getByRole("button", { name: "Plus d'actions" }).click()
    await page.getByRole("button", { name: "Publier" }).click()
    await expect(page.locator(".messages .success")).toBeVisible()

    await page.goto("/guides/?category=alsace")
    await chip(page, name).click()
    await expect(page).toHaveURL(/category=bas-rhin/)
    await expectGuides(page, [STRASBOURG])

    await page.goto(categories)
    await page.getByRole("radio", { name: "Arborescence complète" }).check()
    await page.getByRole("button", { name: `Plus d’options pour « ${name} »` }).click()
    await page.getByRole("link", { name: "Supprimer" }).click()
    await page.getByRole("button", { name: /Oui, supprimer/ }).click()
    await expect(page.locator(".messages .success")).toBeVisible()

    await page.goto("/guides/?category=alsace")
    await expectGuides(page, [STRASBOURG])
    await expect(chip(page, name)).toHaveCount(0)
  })
})
