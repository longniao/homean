import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/config";
import { resources } from "@/lib/resources";
export const dynamic = "force-static";
const sitemap = (): MetadataRoute.Sitemap => ["/", "/how-it-works/", "/resources/", ...resources.map(item => `/resources/${item.slug}/`)].map(path => ({ url: new URL(path, siteConfig.siteUrl).toString(), lastModified: new Date("2026-09-10"), changeFrequency: "monthly", priority: path === "/" ? 1 : 0.7 }));
export default sitemap;
