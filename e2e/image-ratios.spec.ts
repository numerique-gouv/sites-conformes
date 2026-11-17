import { execFileSync } from "child_process";
import { expect, type Locator, type Page } from "@playwright/test";
import { test } from "./fixtures";

// Display options of #597 (images no longer cropped against the editor's will).
// The pages are created by image_ratios_fixtures.py, with a 2:1 image.
const SOURCE_RATIO = 2;
const TOLERANCE = 0.02;

const ratios: Record<string, number> = {
  "1x1": 1,
  "16x9": 16 / 9,
  "3x2": 3 / 2,
  "4x3": 4 / 3,
  "3x4": 3 / 4,
  "2x3": 2 / 3,
  "32x9": 32 / 9,
};

function expectRatio(actual: number, expected: number, what: string) {
  expect(
    Math.abs(actual / expected - 1),
    `${what}: ${actual} ≠ ${expected}`,
  ).toBeLessThan(TOLERANCE);
}

async function measureImage(img: Locator) {
  await expect(img).toBeVisible();
  await expect
    .poll(() =>
      img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth),
    )
    .toBeTruthy();
  return img.evaluate((el: HTMLImageElement) => {
    const { width, height } = el.getBoundingClientRect();
    return {
      width,
      ratio: width / height,
      naturalWidth: el.naturalWidth,
      naturalRatio: el.naturalWidth / el.naturalHeight,
      objectFit: getComputedStyle(el).objectFit,
    };
  });
}

// Shown in the expected shape, and cropped rather than stretched to it
async function expectImageShape(img: Locator, ratio: number) {
  const image = await measureImage(img);
  expectRatio(image.ratio, ratio, "displayed ratio");
  if (image.objectFit !== "cover") {
    expectRatio(image.naturalRatio, ratio, "delivered image ratio");
  }
  return image;
}

async function open(page: Page, slug: string) {
  const response = await page.goto(`/e2e-image-ratios/${slug}/`);
  expect(response?.status()).toBe(200);
}

test.describe("Formats d’image (#597)", () => {
  test.beforeAll(() => {
    execFileSync(
      "uv",
      [
        "run",
        "python",
        "manage.py",
        "shell",
        "-c",
        "exec(open('e2e/image_ratios_fixtures.py').read())",
      ],
      { stdio: "inherit" },
    );
  });

  test.describe("En-tête image et texte", () => {
    const heroImage = (page: Page) => page.locator(".cmsfr-hero-media img");

    test("Les proportions d’origine ne rognent pas l’image", async ({
      page,
    }) => {
      await open(page, "hero-original");
      const image = await expectImageShape(heroImage(page), SOURCE_RATIO);
      expectRatio(image.naturalRatio, SOURCE_RATIO, "delivered image ratio");
    });

    for (const [format, ratio] of Object.entries(ratios)) {
      test(`Le format ${format} recadre l’image à ce ratio`, async ({
        page,
      }) => {
        await open(page, `hero-${format}`);
        await expectImageShape(heroImage(page), ratio);
      });
    }

    for (const [size, share] of [
      ["sm", 0.5],
      ["md", 0.75],
      ["original", 1],
    ] as const) {
      test(`La taille ${size} occupe ${share * 100} % de la colonne`, async ({
        page,
      }) => {
        await open(
          page,
          size === "original" ? "hero-original" : `hero-size-${size}`,
        );
        const media = page.locator(".cmsfr-hero-media");
        const widths = await media.evaluate((el) => [
          el.getBoundingClientRect().width,
          el.parentElement!.clientWidth,
        ]);
        expectRatio(widths[0] / widths[1], share, "share of the column");
        await expectImageShape(heroImage(page), SOURCE_RATIO);
      });
    }
  });

  test.describe("En-tête avec image de fond", () => {
    const hero = (page: Page) => page.locator(".cmsfr-hero");

    test("Le format standard garde une hauteur minimale de 650 px", async ({
      page,
    }) => {
      await open(page, "background-standard");
      expect((await hero(page).boundingBox())!.height).toBeGreaterThanOrEqual(
        650,
      );
    });

    for (const format of ["32x9", "16x9"]) {
      test(`Le format ${format} donne ce ratio à la bannière`, async ({
        page,
      }) => {
        await open(page, `background-${format}`);
        const box = (await hero(page).boundingBox())!;
        expectRatio(box.width / box.height, ratios[format], "banner ratio");
      });
    }

    test("L’image de fond n’est pas rognée côté serveur", async ({ page }) => {
      await open(page, "background-16x9");
      const naturalRatio = await hero(page).evaluate(async (el) => {
        const url =
          getComputedStyle(el).backgroundImage.match(/url\("?([^")]+)"?\)/)![1];
        const image = new Image();
        image.src = url;
        await image.decode();
        return image.naturalWidth / image.naturalHeight;
      });
      expectRatio(naturalRatio, SOURCE_RATIO, "background image ratio");
    });
  });

  test.describe("Image centrée", () => {
    const centeredImage = (page: Page, caption: string) =>
      page
        .locator("figure", { has: page.getByText(caption, { exact: true }) })
        .locator("img");

    test("Les proportions d’origine ne rognent pas l’image, quelle que soit la largeur", async ({
      page,
    }) => {
      await open(page, "centered-images");
      const widths = [];
      for (const width of ["sm", "md", "lg"]) {
        const image = await expectImageShape(
          centeredImage(page, `original-${width}`),
          SOURCE_RATIO,
        );
        expectRatio(image.naturalRatio, SOURCE_RATIO, "delivered image ratio");
        widths.push(image.width);
      }
      expect(widths[0]).toBeLessThan(widths[1]);
      expect(widths[1]).toBeLessThan(widths[2]);
    });

    test("La taille réelle affiche l’image à sa taille en pixels", async ({
      page,
    }) => {
      await open(page, "centered-images");
      const image = await expectImageShape(
        centeredImage(page, "natural"),
        SOURCE_RATIO,
      );
      expect(image.width).toBe(image.naturalWidth);
    });

    for (const [format, ratio] of Object.entries(ratios)) {
      test(`Le ratio ${format} recadre l’image à ce ratio`, async ({
        page,
      }) => {
        await open(page, "centered-images");
        await expectImageShape(
          centeredImage(page, `fr-ratio-${format}`),
          ratio,
        );
      });
    }
  });
});
