import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/config";
import { publicPages } from "@/lib/public-pages";
export const dynamic = "force-static";
const sitemap = (): MetadataRoute.Sitemap => publicPages.map(({ path, updatedAt }) => ({ url: new URL(path, siteConfig.siteUrl).toString(), lastModified: new Date(updatedAt), changeFrequency: "monthly", priority: path === "/" ? 1 : 0.7 }));
export default sitemap;
