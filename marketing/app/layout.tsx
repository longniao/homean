import { MarketingMeasurement } from "@/components/marketing-measurement";
import type { Metadata } from "next";
import { content } from "@/lib/content";
import { siteConfig } from "@/lib/config";
import "./globals.css";
import "./design.css";
import "./resources.css";

export const metadata: Metadata = {
  metadataBase: new URL(siteConfig.siteUrl),
  verification: { google: "hFGH3XdT8pwSB3sVbriK0eXzVyrDw_F9mEL3qMFTBPY" },
  title: content.metadata.title,
  description: content.metadata.description,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: siteConfig.siteUrl,
    title: content.metadata.title,
    description: content.metadata.socialDescription,
    siteName: content.brandName,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: content.metadata.socialAlt }],
  },
  twitter: {
    card: "summary_large_image",
    title: content.metadata.title,
    description: content.metadata.twitterDescription,
    images: ["/og.png"],
  },
  robots: { index: siteConfig.indexable, follow: siteConfig.indexable },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}<MarketingMeasurement signupUrl={siteConfig.signupUrl} /></body></html>;
}
