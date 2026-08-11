export const ACCESS_COOKIE = "homean_access";
export const REFRESH_COOKIE = "homean_refresh";
export const LEGACY_ACCESS_COOKIE = "kawu_access";
export const LEGACY_REFRESH_COOKIE = "kawu_refresh";

export const ACCESS_COOKIE_NAMES = [ACCESS_COOKIE, LEGACY_ACCESS_COOKIE] as const;
export const REFRESH_COOKIE_NAMES = [REFRESH_COOKIE, LEGACY_REFRESH_COOKIE] as const;

export const backendUrl = () =>
  (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
