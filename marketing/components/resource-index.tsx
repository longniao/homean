import Link from "next/link";
import { resources, resourceCopy } from "@/lib/resources";
export function ResourceIndex({ primary = false }: { primary?: boolean }) {
  const Heading = primary ? "h1" : "h2";
  const CardHeading = primary ? "h2" : "h3";
  return <section className="resource-index section-shell" aria-labelledby="resources-title"><p className="eyebrow">{resourceCopy.eyebrow}</p><Heading id="resources-title">{primary ? resourceCopy.indexTitle : resourceCopy.title}</Heading><p className="resource-lead">{resourceCopy.description}</p>{primary && <p className="resource-byline"><Link href="/about/#editorial">{resourceCopy.editorialLink} →</Link></p>}<div className="resource-grid">{resources.map(resource => <article className="resource-card" key={resource.slug}><p className="eyebrow">{resource.eyebrow}</p><CardHeading><Link href={`/resources/${resource.slug}/`}>{resource.title}</Link></CardHeading><p>{resource.description}</p><Link className="text-link" href={`/resources/${resource.slug}/`}>{resourceCopy.read} <span aria-hidden="true">↗</span></Link></article>)}</div></section>;
}
