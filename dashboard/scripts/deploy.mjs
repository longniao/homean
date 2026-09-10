import { spawnSync } from 'node:child_process';

const value = process.env.HOMEAN_API_URL;
if (!value) throw new Error('Set HOMEAN_API_URL to the provisioned HTTPS backend origin before deploying.');
const url = new URL(value);
if (url.protocol !== 'https:' || url.hostname.endsWith('.invalid') || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
  throw new Error('HOMEAN_API_URL must be a real HTTPS origin, without credentials, query or path.');
}
const response = await fetch(new URL('/ready', url), { signal: AbortSignal.timeout(15_000) });
const health = await response.json();
if (!response.ok || health.status !== 'ok' || ['database', 'redis', 's3'].some(key => health.checks?.[key] !== 'ok')) {
  throw new Error('Backend readiness failed; dashboard was not deployed.');
}
for (const args of [['run', 'cf:build'], ['exec', '--', 'opennextjs-cloudflare', 'deploy', '--var', `HOMEAN_API_URL:${url.origin}`]]) {
  const result = spawnSync('npm', args, { stdio: 'inherit', env: process.env });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
