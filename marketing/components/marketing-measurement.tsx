"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";

export function referralCategory(referrer: string, query: string): string {
  if (new URLSearchParams(query).get("utm_source") === "chatgpt.com") return "chatgpt";
  if (!referrer) return "direct";
  try {
    const host = new URL(referrer).hostname;
    if (host === "chatgpt.com" || host.endsWith(".chatgpt.com")) return "chatgpt";
    if (host === "bing.com" || host.endsWith(".bing.com")) return "bing";
    if (/^(www\.)?google\.(com|ca|co\.uk|com\.au)$/.test(host)) return "google";
    if (host === "homean.com") return "internal";
  } catch { return "other"; }
  return "other";
}

export function MarketingMeasurement({ signupUrl }: { signupUrl: string }) {
  const pathname = usePathname();
  useEffect(() => {
    if (window.location.hostname !== "homean.com" || navigator.doNotTrack === "1" || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl) return;
    const source = referralCategory(document.referrer, window.location.search);
    const path = pathname.endsWith("/") ? pathname : `${pathname}/`;
    const measure = (event: string) => {
      const query = new URLSearchParams({ event, path, source });
      void fetch(`/_events?${query}`, { method: "POST", keepalive: true, credentials: "omit", referrerPolicy: "no-referrer" }).catch(() => {});
    };
    measure("page_view");
    const click = (event: MouseEvent) => {
      const element = event.target instanceof Element ? event.target.closest<HTMLElement>("a,button") : null;
      if (!element) return;
      if (element.dataset.measure) measure(element.dataset.measure);
      else if (element instanceof HTMLAnchorElement && element.href === signupUrl) measure("signup_click");
    };
    document.addEventListener("click", click);
    return () => document.removeEventListener("click", click);
  }, [pathname, signupUrl]);
  return null;
}
