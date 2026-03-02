import { test as base, expect } from "@playwright/test"

export const test = base.extend<{ forEachTest: void }>({
  forEachTest: [
    async ({ page }, use, testInfo) => {
      await use()
      if (testInfo.tags.includes("@regression")) {
        await expect.soft(page).toHaveScreenshot({ fullPage: true })
      }
    },
    { auto: true },
  ],
})
