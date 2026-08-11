import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "../backend/.venv/bin/python e2e/backend_server.py",
      gracefulShutdown: { signal: "SIGTERM", timeout: 10_000 },
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "PORT=3001 HOSTNAME=127.0.0.1 NEXT_PUBLIC_API_URL=http://127.0.0.1:8001 node .next/standalone/server.js",
      url: "http://127.0.0.1:3001/login",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
