import { defineConfig, PlaywrightTestConfig } from "@playwright/test"
import dotenv from "dotenv"
import path from "path"
import { fileURLToPath } from "url"

/**
 * See https://playwright.dev/docs/test-configuration.
 *
 * Environment management mirrors the quefairedemesobjets webapp config:
 * load the project's .env, then inject the variables the Django dev server
 * needs into the webServer process so the test run is self-contained.
 */

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: path.resolve(__dirname, ".env") })

const PORT = 8000
const BASE_URL = `http://127.0.0.1:${PORT}`

export const config: PlaywrightTestConfig = {
  testDir: "./e2e",
  timeout: 45000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 1,
  workers: 1,
  reporter: process.env.CI ? "blob" : "html",
  // Start the Django dev server for the test run, or reuse one already running
  // on PORT. Locally (reuseExistingServer) it picks up a server you started by
  // hand; in CI it launches its own with the env injected below.
  webServer: {
    command: `uv run python manage.py runserver 127.0.0.1:${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    cwd: path.resolve(__dirname),
    env: {
      ...(process.env as Record<string, string>),
      DATABASE_URL: process.env.DATABASE_URL!,
      SECRET_KEY: process.env.SECRET_KEY!,
      DEBUG: process.env.DEBUG ?? "True",
      BASE_URL,
    },
  },
  use: {
    baseURL: BASE_URL,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  expect: {
    toHaveScreenshot: {
      pathTemplate: `./__screenshots__/{testFilePath}/{testName}/{arg}{ext}`,
      maxDiffPixelRatio: 0.01,
    },
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
}

export default defineConfig(config)
