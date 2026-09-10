import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { howItWorks as copy } from "@/lib/how-it-works";
import { contactMailto, siteConfig } from "@/lib/config";
export const metadata: Metadata = { title: `${copy.title} | Homean`, description: copy.description, alternates: { canonical: "/how-it-works/" }, openGraph: { title: `${copy.title} | Homean`, description: copy.description, url: "/how-it-works/" } };
export default function HowItWorksPage() { return <><SiteHeader /><main id="main-content" className="resource-page section-shell"><header className="resource-heading"><p className="eyebrow">{copy.eyebrow}</p><h1>{copy.title}</h1><p className="resource-lead">{copy.intro}</p></header><aside className="beta-note"><h2>{copy.availabilityTitle}</h2><p>{copy.availability}</p></aside><article className="resource-body">{copy.sections.map(section => <section key={section.title}><h2>{section.title}</h2><p>{section.text}</p></section>)}</article><div className="resource-actions"><a className="button button-dark" href={siteConfig.signupUrl}>{copy.cta}</a><Link className="text-link" href="/resources/">{copy.samples} →</Link></div><p className="resource-contact">{copy.contact} <a href={contactMailto()}>{siteConfig.contactEmail}</a></p></main></>; }
