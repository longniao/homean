export const ACCESS_COOKIE = "kawu_access";
export const REFRESH_COOKIE = "kawu_refresh";

export const backendUrl = () =>
  (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
