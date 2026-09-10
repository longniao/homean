import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/config";
export const dynamic = "force-static";
const robots = (): MetadataRoute.Robots => ({
  rules: siteConfig.indexable
    ? [{ userAgent: "*", allow: "/", disallow: "/_events" }, { userAgent: "OAI-SearchBot", allow: "/", disallow: "/_events" }, { userAgent: "GPTBot", disallow: "/" }]
    : { userAgent: "*", disallow: "/" },
  sitemap: siteConfig.indexable ? `${siteConfig.siteUrl}/sitemap.xml` : undefined,
});
export default robots;
