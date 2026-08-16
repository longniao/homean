import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/config";

export const dynamic = "force-static";

const sitemap = (): MetadataRoute.Sitemap => [
  {
    url: siteConfig.siteUrl,
    lastModified: new Date("2026-08-15"),
    changeFrequency: "monthly",
    priority: 1,
  },
];

export default sitemap;
