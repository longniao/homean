import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { ACCESS_COOKIE, backendUrl, REFRESH_COOKIE } from "@/lib/auth";

type TokenPayload = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

async function forward(
  request: NextRequest,
  path: string,
  accessToken: string | undefined,
) {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  return fetch(`${backendUrl()}/${path}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
  });
}

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const cookieStore = await cookies();
  let accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  let upstream = await forward(request, path.join("/"), accessToken);
  let refreshed: TokenPayload | null = null;

  if (upstream.status === 401 && refreshToken) {
    const refresh = await fetch(`${backendUrl()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (refresh.ok) {
      refreshed = (await refresh.json()) as TokenPayload;
      accessToken = refreshed.access_token;
      upstream = await forward(request, path.join("/"), accessToken);
    }
  }

  const response = new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
    },
  });
  if (refreshed) {
    const common = {
      httpOnly: true,
      sameSite: "lax" as const,
      secure: process.env.NODE_ENV === "production",
      path: "/",
    };
    response.cookies.set(ACCESS_COOKIE, refreshed.access_token, {
      ...common,
      maxAge: refreshed.expires_in,
    });
    response.cookies.set(REFRESH_COOKIE, refreshed.refresh_token, {
      ...common,
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  return response;
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
