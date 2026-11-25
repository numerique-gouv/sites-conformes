import { expect } from "@playwright/test"
import { test } from "./fixtures"

// These scenarios rely on the content created by
// `python manage.py create_e2e_pages` (numerique_gouv app).

test.describe("News", () => {
  test(
    "the news index renders",
    { tag: "@regression" },
    async ({ page }) => {
      const response = await page.goto("/actualites/")
      expect(response?.status()).toBe(200)
      const main = page.locator("main")
      await expect(main.getByRole("heading", { level: 1 })).toContainText("Actualités")
      await expect(main.getByRole("link", { name: "Lancement de l’offre d’accompagnement IA" })).toBeVisible()
      await expect(main.getByRole("link", { name: "Nouvelle stratégie cloud de l’État" })).toBeVisible()
    },
  )

  test("filtering by tag narrows the list", async ({ page }) => {
    await page.goto("/actualites/")
    const main = page.locator("main")
    await main.locator("a.fr-tag", { hasText: "Intelligence artificielle" }).click()

    await expect(page).toHaveURL(/page_tag=ia/)
    await expect(main.locator("a.fr-tag", { hasText: "Intelligence artificielle" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    await expect(main.getByRole("link", { name: "Lancement de l’offre d’accompagnement IA" })).toBeVisible()
    await expect(main.getByRole("link", { name: "L’IA au service des agents publics" })).toBeVisible()
    await expect(main.getByRole("link", { name: "Ouverture des données publiques" })).toHaveCount(0)
  })

  test("a news post renders", async ({ page }) => {
    const response = await page.goto("/actualites/nouvelle-strategie-cloud/")
    expect(response?.status()).toBe(200)
    await expect(page.locator("main h1")).toContainText("Nouvelle stratégie cloud de l’État")
  })

  test("an unknown filter returns a 404", async ({ page }) => {
    const response = await page.goto("/actualites/?page_tag=inconnu")
    expect(response?.status()).toBe(404)
  })
})

test.describe("Offers", () => {
  test(
    "the offers index renders",
    { tag: "@regression" },
    async ({ page }) => {
      const response = await page.goto("/offre-accompagnement/")
      expect(response?.status()).toBe(200)
      const main = page.locator("main")
      await expect(main.getByText("Albert, l’IA des agents publics").first()).toBeVisible()
      await expect(main.getByText("Fonds pour la transformation de l’action publique").first()).toBeVisible()
    },
  )

  test("filtering by tag narrows the offers", async ({ page }) => {
    await page.goto("/offre-accompagnement/")
    const main = page.locator("main")
    await main.locator("a.fr-tag", { hasText: "Intelligence artificielle" }).click()

    await expect(page).toHaveURL(/page_tag=ia/)
    await expect(main.getByText("Albert, l’IA des agents publics").first()).toBeVisible()
    await expect(main.getByText("France transfert")).toHaveCount(0)
  })
})

test.describe("Digital services", () => {
  test(
    "the services index renders",
    { tag: "@regression" },
    async ({ page }) => {
      const response = await page.goto("/services-numeriques/")
      expect(response?.status()).toBe(200)
      const main = page.locator("main")
      await expect(main.getByText("ProConnect").first()).toBeVisible()
      await expect(main.getByText("FranceConnect").first()).toBeVisible()
      await expect(main.getByText("API Entreprise").first()).toBeVisible()
    },
  )

  test("a service page redirects to the services index", async ({ page }) => {
    await page.goto("/services-numeriques/proconnect/")
    await expect(page).toHaveURL(/\/services-numeriques\/$/)
  })
})

test.describe("Hub page", () => {
  test(
    "the hub page gathers the content linked to its tag",
    { tag: "@regression" },
    async ({ page }) => {
      const response = await page.goto("/hub-intelligence-artificielle/")
      expect(response?.status()).toBe(200)
      const main = page.locator("main")
      await expect(main.getByRole("link", { name: "Lancement de l’offre d’accompagnement IA" })).toBeVisible()
      await expect(main.getByRole("link", { name: "Conseil en intelligence artificielle" })).toBeVisible()
      await expect(main.getByText("ProConnect").first()).toBeVisible()
      await expect(main.getByText("Ouverture des données publiques")).toHaveCount(0)
    },
  )
})

test.describe("Sitemap", () => {
  test(
    "the sitemap lists the published pages",
    { tag: "@regression" },
    async ({ page }) => {
      const response = await page.goto("/a-propos-numerique/carte-du-site/")
      expect(response?.status()).toBe(200)
      const main = page.locator("main")
      await expect(main.locator(`a[href="/actualites/"]`)).toHaveText("Actualités")
      await expect(main.getByRole("link", { name: "Services numériques", exact: true })).toBeVisible()
    },
  )
})
