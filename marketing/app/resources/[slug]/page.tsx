import { HomeComparison } from "@/components/home-comparison";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteHeader } from "@/components/site-header";
import { ResourceTools } from "@/components/resource-tools";
import { resources, resourceCopy } from "@/lib/resources";
import { siteConfig } from "@/lib/config";
export function generateStaticParams() { return resources.map(({ slug }) => ({ slug })); }
export const dynamicParams = false;
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params; const resource = resources.find(item => item.slug === slug); if (!resource) notFound();
  return { title: `${resource.title} | Homean`, description: resource.description, alternates: { canonical: `/resources/${slug}/` }, openGraph: { title: `${resource.title} | Homean`, description: resource.description, url: `/resources/${slug}/` }, twitter: { title: `${resource.title} | Homean`, description: resource.description } };
}
export default async function ResourcePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const resource = resources.find(item => item.slug === slug); if (!resource) notFound();
  const schema = { "@context": "https://schema.org", "@type": "Article", headline: resource.title, description: resource.description, dateModified: "2026-09-10", author: { "@type": "Organization", name: "Homean", url: siteConfig.siteUrl }, mainEntityOfPage: `${siteConfig.siteUrl}/resources/${slug}/` };
  return <><SiteHeader /><main id="main-content" className={`resource-page section-shell${slug === "home-comparison-worksheet" ? " comparison-worksheet-page" : ""}`}><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} /><Link className="text-link no-print" href="/resources/">← {resourceCopy.home}</Link><header className="resource-heading"><p className="eyebrow">{resource.eyebrow}</p><h1>{resource.title}</h1><p className="resource-lead">{resource.intro}</p><p className="resource-byline">Homean · {resourceCopy.updated}</p><ResourceTools download={resource.download} /></header>{slug === "home-comparison-worksheet" && <HomeComparison />}<article className="resource-body">{resource.sections.map((section) => <section key={section.title}><h2>{section.title}</h2><p>{section.text}</p>{section.bullets && <ul>{section.bullets.map(item => <li key={item}>{item}</li>)}</ul>}</section>)}</article><aside className="resource-next no-print"><h2>{resourceCopy.nextTitle}</h2><p>{resourceCopy.nextText}</p><Link className="text-link" href="/how-it-works/">{resourceCopy.nextLink} ↗</Link></aside><nav className="resource-related no-print" aria-label={resourceCopy.related}>{resources.filter(item => item.slug !== slug).map(item => <Link key={item.slug} href={`/resources/${item.slug}/`}>{item.title} →</Link>)}</nav></main></>;
}
