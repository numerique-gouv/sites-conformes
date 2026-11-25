import { test as base, expect } from "@playwright/test"

// When set (the PR carries the `visual-change` label, see ci-e2e.yml), a
// visual diff is reported but does not fail the test.
const allowVisualDiff = process.env.ALLOW_VISUAL_DIFF === "true"

// After every test tagged @regression, capture a full-page screenshot and
// assert it against the baseline. The assertion is intentionally hard (not
// `expect.soft`): in comparison mode a visual diff must fail the run, unless
// ALLOW_VISUAL_DIFF is set. In baseline mode the suite runs with
// --update-snapshots, so this writes the baseline image and passes.
export const test = base.extend<{ forEachTest: void }>({
  forEachTest: [
    async ({ page }, use, testInfo) => {
      await use()
      if (testInfo.tags.includes("@regression")) {
        try {
          await expect(page).toHaveScreenshot({ fullPage: true })
        } catch (error) {
          if (!allowVisualDiff) throw error
          // The expected/actual/diff images are still written to test-results/.
          testInfo.annotations.push({
            type: "visual-diff",
            description: error instanceof Error ? error.message : String(error),
          })
        }
      }
    },
    { auto: true },
  ],
})
