import Link from "next/link";
import { ResourceIndex } from "@/components/resource-index";
import { howItWorks } from "@/lib/how-it-works";
import { Faq } from "@/components/faq";
import { ProductComposition } from "@/components/product-composition";
import { SignupCta } from "@/components/signup-cta";
import { SiteHeader } from "@/components/site-header";
import { Trust } from "@/components/trust";
import { Workflow } from "@/components/workflow";
import { content } from "@/lib/content";
import { contactMailto, siteConfig } from "@/lib/config";

export default function HomePage() {
  return (
    <>
      <a className="skip-link" href="#main-content">{content.accessibility.skipToMain}</a>
      <SiteHeader />
      <main id="main-content">
      <section className="hero section-shell" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow reveal reveal-one">{content.hero.eyebrow}</p>
          <h1 id="hero-title" className="reveal reveal-two">{content.hero.title}</h1>
          <p className="hero-description reveal reveal-three">{content.hero.description}</p>
          <div className="hero-actions reveal reveal-four"><a className="button button-dark" href={siteConfig.signupUrl}>{content.hero.primaryCta}<span aria-hidden="true">↗</span></a><Link className="text-link" href="/resources/home-comparison-worksheet/" data-measure="comparison_tool_click">{content.hero.secondaryCta}<span aria-hidden="true">→</span></Link></div>
          <p className="hero-note reveal reveal-four"><span className="tiny-square" aria-hidden="true" />{content.hero.note}</p>
        </div>
        <div className="hero-composition reveal reveal-three"><ProductComposition compact /></div>
        <div className="hero-side-note" aria-hidden="true"><span>{content.hero.sideNote[0]}</span><span>{content.hero.sideNote[1]}</span></div>
      </section>

      <section className="problem-section section-shell" id="for-agents" aria-labelledby="problem-title">
        <div className="problem-heading"><p className="eyebrow">{content.problem.eyebrow}</p><h2 id="problem-title">{content.problem.title}</h2><p>{content.problem.description}</p></div>
        <div className="workflow-contrast" aria-label={content.problem.contrastLabel}>
          <div className="contrast-column scattered"><p className="contrast-label">{content.problem.scatteredLabel}</p>{content.problem.scatteredItems.map((item, index) => <div className="contrast-item" key={item}><span>{String(index + 1).padStart(2, "0")}</span>{item}<i aria-hidden="true">×</i></div>)}</div>
          <div className="contrast-arrow" aria-hidden="true">→</div>
          <div className="contrast-column collected"><p className="contrast-label">{content.problem.collectedLabel}</p>{content.problem.collectedItems.map((item, index) => <div className="contrast-item" key={item}><span>{String(index + 1).padStart(2, "0")}</span>{item}<i aria-hidden="true">✓</i></div>)}</div>
        </div>
      </section>

      <aside className="beta-banner section-shell"><strong>{howItWorks.eyebrow}.</strong> {howItWorks.availability} <Link href="/how-it-works/">{content.nav.howItWorks} →</Link></aside>
      <Workflow />

      <section className="proof-section section-shell" aria-labelledby="proof-title">
        <div className="proof-heading"><p className="eyebrow">{content.productProof.eyebrow}</p><h2 id="proof-title">{content.productProof.title}</h2><p>{content.productProof.description}</p></div>
        <ProductComposition />
      </section>

      <section className="agents-section section-shell" aria-labelledby="agents-title">
        <div className="agents-copy"><p className="eyebrow">{content.agents.eyebrow}</p><h2 id="agents-title">{content.agents.title}</h2><p>{content.agents.description}</p><a className="text-link" href={siteConfig.signupUrl}>{content.agents.signupLink} <span aria-hidden="true">↗</span></a></div>
        <div className="agent-points">{content.agents.points.map((point, index) => <article className="agent-point" key={point.title}><span className="agent-point-mark">{["✳", "□", "↗"][index]}</span><div><h3>{point.title}</h3><p>{point.description}</p></div></article>)}</div>
      </section>

      <Trust />
      <ResourceIndex />
      <SignupCta />
      <Faq />

      <footer className="site-footer section-shell">
        <div className="footer-brand"><span className="wordmark-mark" aria-hidden="true">H</span><span>{content.brandName}</span><p>{content.footer.line}</p></div>
        <div className="footer-meta"><p>{content.footer.availability}</p><p>{content.footer.privacy}</p><div className="footer-links"><Link href="/resources/">{content.nav.resources}</Link><Link href="/how-it-works/">{content.nav.howItWorks}</Link><a href={siteConfig.appUrl}>{content.nav.signIn}</a><a href={contactMailto()}>{siteConfig.contactEmail}</a></div></div>
        <p className="footer-legal">{content.footer.copyright} <span>{content.footer.signature}</span></p>
      </footer>
      </main>
    </>
  );
}
