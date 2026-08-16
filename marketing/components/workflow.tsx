import { content } from "@/lib/content";

export function Workflow() {
  return (
    <section className="workflow-section section-shell" id="how-it-works" aria-labelledby="workflow-title">
      <div className="section-heading split-heading">
        <div><p className="eyebrow">{content.workflow.eyebrow}</p><h2 id="workflow-title">{content.workflow.title}</h2></div>
        <p className="section-intro">{content.workflow.description}</p>
      </div>
      <div className="workflow-list">
        {content.workflow.steps.map((step) => (
          <article className="workflow-step" key={step.number}>
            <div className="step-number">{step.number}</div>
            <div className="step-copy"><h3>{step.title}</h3><p>{step.description}</p></div>
            <div className="step-detail">{step.detail}</div>
          </article>
        ))}
      </div>
    </section>
  );
}
