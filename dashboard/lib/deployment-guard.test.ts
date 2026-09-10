// @vitest-environment node
import { spawnSync } from 'node:child_process';
import { expect, it } from 'vitest';
it.each(['', 'https://homean-api-unconfigured.invalid', 'http://api.example.com'])('refuses deployment before any build/upload for origin %s', (origin) => {
  const result = spawnSync(process.execPath, ['scripts/deploy.mjs'], { env: { ...process.env, HOMEAN_API_URL: origin } as NodeJS.ProcessEnv, encoding: 'utf8' });
  expect(result.status).not.toBe(0);
  expect(result.stderr).toContain('HOMEAN_API_URL');
  expect(result.stdout).not.toContain('OpenNext');
});
