import type { Metadata } from "next";
import { SiteHeader } from "@/components/site-header";
import { ResourceIndex } from "@/components/resource-index";
import { resourceCopy } from "@/lib/resources";
export const metadata: Metadata = { title: "Free showing report templates & home comparison resources | Homean", description: resourceCopy.description, alternates: { canonical: "/resources/" }, openGraph: { url: "/resources/", title: "Free showing resources | Homean", description: resourceCopy.description } };
export default function ResourcesPage() { return <><SiteHeader /><main id="main-content"><ResourceIndex primary /></main></>; }
