import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HomeComparison } from "@/components/home-comparison";
import { SiteHeader } from "@/components/site-header";
import { ResourceTools } from "@/components/resource-tools";
import { StructuredData } from "@/components/structured-data";
import { resources, resourceCopy } from "@/lib/resources";
import { resourceAnswers, editorialCopy as copy } from "@/lib/resource-answers";
import { resourceSchema } from "@/lib/discovery";
import { displayDate, updatedAt } from "@/lib/public-pages";

export function generateStaticParams() {
  return resources.map(({ slug }) => ({ slug }));
}
export const dynamicParams = false;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const resource = resources.find(item => item.slug === slug);
  if (!resource) notFound();
  const title = `${resource.title} | Homean`;
  const path = `/resources/${slug}/`;
  return {
    title, description: resource.description,
    alternates: { canonical: path },
    openGraph: {
      type: "article", title, description: resource.description, url: path,
      publishedTime: "2026-09-10", modifiedTime: updatedAt(path),
      images: [{ url: "/og.png", width: 1200, height: 630, alt: resource.title }],
    },
    twitter: { card: "summary_large_image", title, description: resource.description, images: ["/og.png"] },
  };
}

export default async function ResourcePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const resource = resources.find(item => item.slug === slug);
  if (!resource) notFound();
  const answers = resourceAnswers[slug];
  const date = updatedAt(`/resources/${slug}/`);
  return <><SiteHeader />
    <main id="main-content" className={`resource-page section-shell${slug === "home-comparison-worksheet" ? " comparison-worksheet-page" : ""}`}>
      <StructuredData value={resourceSchema(resource)} />
      <nav className="resource-breadcrumbs no-print" aria-label={copy.breadcrumb}>
        <ol><li><Link href="/">{copy.home}</Link></li><li><Link href="/resources/">{copy.resources}</Link></li><li aria-current="page">{resource.title}</li></ol>
      </nav>
      <header className="resource-heading">
        <p className="eyebrow">{resource.eyebrow}</p><h1>{resource.title}</h1>
        <p className="resource-lead">{resource.intro}</p>
        <p className="resource-byline">{copy.by} <Link href="/about/">Homean</Link> · {copy.updated} <time dateTime={date}>{displayDate(date)}</time></p>
        <ResourceTools download={resource.download} />
      </header>
      <section className="resource-answer no-print" aria-labelledby="quick-answer">
        <p className="eyebrow">{resourceCopy.quickAnswer}</p>
        <h2 id="quick-answer">{answers.question}</h2><p>{answers.answer}</p>
      </section>
      {slug === "home-comparison-worksheet" && <HomeComparison />}
      <nav className="resource-contents no-print" aria-label={copy.contents}>
        <p className="eyebrow">{copy.contents}</p>
        <ul>{resource.sections.map((section, index) => <li key={section.title}><a href={`#section-${index + 1}`}>{section.title}</a></li>)}<li><a href="#questions">{copy.answersTitle}</a></li></ul>
      </nav>
      <article className={`resource-body${resource.sections.some(section => section.example) ? " resource-body-examples" : ""}`}>
        {resource.sections.map((section, index) => <section id={`section-${index + 1}`} key={section.title} className={section.example ? "resource-section-example" : undefined}>
          <div><h2>{section.title}</h2><p>{section.text}</p>{section.bullets && <ul>{section.bullets.map(item => <li key={item}>{item}</li>)}</ul>}</div>
          {section.example && <aside className="resource-filled-example"><p className="eyebrow">{resourceCopy.exampleLabel}</p><p>{section.example}</p></aside>}
        </section>)}
      </article>
      <section className="resource-questions no-print" id="questions" aria-labelledby="questions-title">
        <p className="eyebrow">{copy.answersTitle}</p>
        <h2 id="questions-title">{resourceCopy.questionsTitle}</h2>
        {answers.questions.map(item => <div className="resource-question" key={item.question}><h3>{item.question}</h3><p>{item.answer}</p></div>)}
      </section>
      <aside className="resource-editorial no-print">
        <h2>{copy.formatTitle}</h2><p>{copy.formatText} <Link href="/about/#editorial">{copy.policyLink} →</Link></p>
        {answers.inspectionSource && <><h3>{copy.sourceTitle}</h3><p>{copy.sourceContext}</p><a href={copy.sourceUrl}>{copy.sourceLabel} ↗</a></>}
      </aside>
      <aside className="resource-next no-print"><p className="eyebrow">{copy.next}</p><h2><Link href={`/resources/${answers.nextSlug}/`}>{answers.nextLabel} →</Link></h2><p>{resourceCopy.nextText}</p><Link className="text-link" href="/how-it-works/">{resourceCopy.nextLink} ↗</Link></aside>
      <nav className="resource-related no-print" aria-label={resourceCopy.related}>{resources.filter(item => item.slug !== slug).map(item => <Link key={item.slug} href={`/resources/${item.slug}/`}>{item.title} →</Link>)}</nav>
    </main>
  </>;
}
