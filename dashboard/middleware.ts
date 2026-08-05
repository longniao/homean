import { NextRequest, NextResponse } from "next/server";

import { ACCESS_COOKIE } from "@/lib/auth";

export function middleware(request: NextRequest) {
  const authenticated = Boolean(request.cookies.get(ACCESS_COOKIE)?.value);
  const isAuthPage = ["/login", "/signup"].includes(request.nextUrl.pathname);

  if (!authenticated && !isAuthPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  if (authenticated && isAuthPage) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
