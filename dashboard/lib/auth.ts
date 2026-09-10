export const ACCESS_COOKIE = "homean_access";
export const REFRESH_COOKIE = "homean_refresh";
export const LEGACY_ACCESS_COOKIE = "kawu_access";
export const LEGACY_REFRESH_COOKIE = "kawu_refresh";

export const ACCESS_COOKIE_NAMES = [ACCESS_COOKIE, LEGACY_ACCESS_COOKIE] as const;
export const REFRESH_COOKIE_NAMES = [REFRESH_COOKIE, LEGACY_REFRESH_COOKIE] as const;

export const backendUrl = () =>
  (
    process.env.HOMEAN_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");

/** Give clients a retryable response when the configured API is unavailable. */
export async function fetchBackend(path: string, init: RequestInit): Promise<Response> {
  try {
    const origin = backendUrl();
    if (new URL(origin).hostname.endsWith(".invalid")) throw new Error("API not configured");
    return await fetch(`${origin}${path}`, init);
  } catch {
    return Response.json({ detail: "Service temporarily unavailable. Please try again later." }, { status: 503 });
  }
}
