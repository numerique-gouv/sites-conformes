import { test as base, expect } from "@playwright/test"

// After every test tagged @regression, capture a full-page screenshot and
// assert it against the baseline. The assertion is intentionally hard (not
// `expect.soft`): in comparison mode a visual diff must fail the run. In
// baseline mode the suite runs with --update-snapshots, so this writes the
// baseline image and passes.
export const test = base.extend<{ forEachTest: void }>({
  forEachTest: [
    async ({ page }, use, testInfo) => {
      await use()
      if (testInfo.tags.includes("@regression")) {
        await expect(page).toHaveScreenshot({ fullPage: true })
      }
    },
    { auto: true },
  ],
})
