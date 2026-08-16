import { content } from "@/lib/content";

export function Faq() {
  return (
    <section className="faq-section section-shell" aria-labelledby="faq-title">
      <div className="faq-heading"><p className="eyebrow">{content.faq.eyebrow}</p><h2 id="faq-title">{content.faq.title}</h2></div>
      <div className="faq-list">
        {content.faq.items.map((item, index) => (
          <details className="faq-item" key={item.question} open={index === 0}>
            <summary><span>{item.question}</span><span className="faq-plus" aria-hidden="true">+</span></summary>
            <p>{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
