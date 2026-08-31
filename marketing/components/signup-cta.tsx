import { content } from "@/lib/content";
import { siteConfig } from "@/lib/config";

export function SignupCta() {
  return (
    <section className="signup-section section-shell" id="signup" aria-labelledby="signup-title">
      <div className="signup-grid">
        <div><p className="eyebrow eyebrow-light">{content.signup.eyebrow}</p><h2 id="signup-title">{content.signup.title}</h2></div>
        <div className="signup-copy"><p>{content.signup.description}</p><a className="button button-signal" href={siteConfig.signupUrl}>{content.signup.cta}<span aria-hidden="true">↗</span></a><p className="signup-note">{content.signup.note}</p></div>
      </div>
    </section>
  );
}
