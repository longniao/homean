import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { StructuredData } from "@/components/structured-data";
import { about } from "@/lib/about";
import { organization } from "@/lib/discovery";
import { contactMailto, siteConfig } from "@/lib/config";
import { displayDate, updatedAt } from "@/lib/public-pages";

export const metadata: Metadata = {
  title: `${about.title} | Homean`, description: about.description,
  alternates: { canonical: "/about/" },
  openGraph: { title: `${about.title} | Homean`, description: about.description, url: "/about/" },
};

export default function AboutPage() {
  const date = updatedAt("/about/");
  return <><SiteHeader /><main id="main-content" className="resource-page section-shell">
    <StructuredData value={{ "@context": "https://schema.org", "@type": "AboutPage", name: about.title, url: `${siteConfig.siteUrl}/about/`, about: { "@id": organization["@id"] }, inLanguage: "en", dateModified: date }} />
    <header className="resource-heading"><p className="eyebrow">{about.eyebrow}</p><h1>{about.title}</h1><p className="resource-lead">{about.intro}</p><p className="resource-byline">{about.updated} <time dateTime={date}>{displayDate(date)}</time></p></header>
    <aside className="beta-note"><h2>{about.availableTitle}</h2><p>{about.availableText}</p><div className="resource-actions"><Link className="text-link" href="/resources/">{about.resourcesLink} →</Link><Link className="text-link" href="/how-it-works/">{about.availabilityLink} →</Link></div></aside>
    <article className="resource-body">{about.sections.map(section => <section id={section.id} key={section.id}><h2>{section.title}</h2><p>{section.text}</p></section>)}<section><h2>{about.contactTitle}</h2><p>{about.contactText}</p><p className="resource-contact"><a href={contactMailto()}>{siteConfig.contactEmail}</a></p></section></article>
  </main></>;
}
