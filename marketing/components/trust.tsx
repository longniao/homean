import { content } from "@/lib/content";

export function Trust() {
  return (
    <section className="trust-section section-shell" id="trust" aria-labelledby="trust-title">
      <div className="trust-heading"><p className="eyebrow">{content.trust.eyebrow}</p><h2 id="trust-title">{content.trust.title}</h2><p>{content.trust.description}</p></div>
      <div className="principles-grid">
        {content.trust.principles.map((principle, index) => (
          <article className="principle" key={principle.label}>
            <span className="principle-index">0{index + 1}</span><h3>{principle.label}</h3><p>{principle.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
