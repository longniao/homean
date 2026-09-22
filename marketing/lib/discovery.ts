import { siteConfig } from "./config";
import { brand } from "./brand";
import { updatedAt } from "./public-pages";
import type { Resource } from "./resources";

const url = (path: string) => new URL(path, siteConfig.siteUrl).toString();
export const organization = {
  "@type": "Organization", "@id": url("/#organization"), name: "Homean",
  url: url("/"), email: siteConfig.contactEmail,
  slogan: brand.slogan,
  description: "An early-beta showing-report tool for buyer’s agents, with free public showing templates and home comparison resources.",
};
export const siteIdentity = {
  "@context": "https://schema.org",
  "@graph": [organization, {
    "@type": "WebSite", "@id": url("/#website"), url: url("/"), name: "Homean",
    inLanguage: "en", publisher: { "@id": organization["@id"] },
  }],
};

export function resourceSchema(resource: Resource) {
  const path = `/resources/${resource.slug}/`;
  return {
    "@context": "https://schema.org",
    "@graph": [{
      "@type": "Article", "@id": url(`${path}#article`),
      headline: resource.title, description: resource.description,
      datePublished: "2026-09-10", dateModified: updatedAt(path), inLanguage: "en",
      author: { "@type": "Organization", "@id": organization["@id"], name: "Homean", url: url("/about/") },
      publisher: { "@id": organization["@id"] },
      mainEntityOfPage: { "@type": "WebPage", "@id": url(path) },
      isAccessibleForFree: true,
    }, {
      "@type": "BreadcrumbList", "@id": url(`${path}#breadcrumbs`),
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Home", item: url("/") },
        { "@type": "ListItem", position: 2, name: "Free resources", item: url("/resources/") },
        { "@type": "ListItem", position: 3, name: resource.title, item: url(path) },
      ],
    }],
  };
}
