import { NextRequest, NextResponse } from "next/server";

import {
  ACCESS_COOKIE,
  backendUrl,
  LEGACY_ACCESS_COOKIE,
  LEGACY_REFRESH_COOKIE,
  REFRESH_COOKIE,
} from "@/lib/auth";

type TokenPayload = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

function setTokenCookies(response: NextResponse, tokens: TokenPayload) {
  const common = {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
  };
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    ...common,
    maxAge: tokens.expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    ...common,
    maxAge: 60 * 60 * 24 * 30,
  });
  response.cookies.delete(LEGACY_ACCESS_COOKIE);
  response.cookies.delete(LEGACY_REFRESH_COOKIE);
}

function clearTokenCookies(response: NextResponse) {
  for (const name of [
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    LEGACY_ACCESS_COOKIE,
    LEGACY_REFRESH_COOKIE,
  ]) {
    response.cookies.delete(name);
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ action: string }> },
) {
  const { action } = await params;
  if (action === "logout") {
    const response = NextResponse.json({ ok: true });
    clearTokenCookies(response);
    return response;
  }
  if (action !== "login" && action !== "signup") {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  const upstream = await fetch(`${backendUrl()}/auth/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await upstream.json();
  const response = NextResponse.json(payload, { status: upstream.status });
  if (upstream.ok) setTokenCookies(response, payload as TokenPayload);
  return response;
}
