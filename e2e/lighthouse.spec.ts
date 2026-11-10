import { chromium, expect, test } from "@playwright/test"

// Demo pages created by `create_demo_pages`, with raster images
const pages = [
  "/menu_page/hero_blocks/hero-text-image/",
  "/menu_page/hero_blocks/hero-text-wide-image/",
  "/menu_page/common_blocks/",
]

// main serves the images of these pages as PNG/JPEG, without width/height:
// the picture tag PR (#672) fixes them and removes this list
const failingOnMain = [
  "/menu_page/hero_blocks/hero-text-image/",
  "/menu_page/common_blocks/",
]

const debuggingPort = 9222

// Lighthouse only gives each image optimization as a message, in English
// unless another locale is set. Responsive images (srcset) are not done yet:
// those optimizations are reported on the test without failing it.
const responsiveSize = /larger than it needs to be/

type NetworkRequest = {
  resourceType: string
  mimeType: string
  statusCode: number
}
type DeliveredImage = { url: string; subItems: { items: { reason: string }[] } }

function detailItems<T>(details: unknown): T[] {
  return (details as { items: T[] }).items
}

test.describe("Lighthouse", () => {
  for (const url of pages) {
    test(`Les images de ${url} passent les audits Lighthouse`, async ({
      baseURL,
    }) => {
      test.slow()
      test.fail(failingOnMain.includes(url))
      // Imported here rather than at the top of the file: the Baseline CI job
      // loads these specs on main, whose node_modules don't have lighthouse
      const { default: lighthouse } = await import("lighthouse")
      const browser = await chromium.launch({
        args: [`--remote-debugging-port=${debuggingPort}`],
      })
      try {
        const result = await lighthouse(new URL(url, baseURL).href, {
          port: debuggingPort,
          logLevel: "error",
          locale: "en-US",
          onlyAudits: [
            "network-requests",
            "image-delivery-insight",
            "unsized-images",
          ],
        })
        const audits = result!.lhr.audits

        // Without loaded images the audits would pass with nothing to check
        const requests = detailItems<NetworkRequest>(
          audits["network-requests"].details,
        )
        expect(
          requests.some(
            (request) =>
              request.resourceType === "Image" &&
              request.mimeType !== "image/svg+xml" &&
              request.statusCode === 200,
          ),
        ).toBe(true)

        expect
          .soft(audits["unsized-images"].score, audits["unsized-images"].title)
          .toBe(1)

        const optimizations = detailItems<DeliveredImage>(
          audits["image-delivery-insight"].details,
        ).flatMap((image) =>
          image.subItems.items.map(({ reason }) => `${image.url}: ${reason}`),
        )
        for (const optimization of optimizations.filter((o) =>
          responsiveSize.test(o),
        )) {
          test.info().annotations.push({
            type: "responsive-images",
            description: optimization,
          })
        }
        expect(optimizations.filter((o) => !responsiveSize.test(o))).toEqual([])
      } finally {
        await browser.close()
      }
    })
  }
})
