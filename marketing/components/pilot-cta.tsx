import { content } from "@/lib/content";
import { pilotMailto } from "@/lib/config";

export function PilotCta() {
  return (
    <section className="pilot-section section-shell" id="pilot" aria-labelledby="pilot-title">
      <div className="pilot-grid">
        <div><p className="eyebrow eyebrow-light">{content.pilot.eyebrow}</p><h2 id="pilot-title">{content.pilot.title}</h2></div>
        <div className="pilot-copy"><p>{content.pilot.description}</p><a className="button button-light" href={pilotMailto()}>{content.pilot.cta}<span aria-hidden="true">↗</span></a><p className="pilot-note">{content.pilot.note}</p></div>
      </div>
    </section>
  );
}
