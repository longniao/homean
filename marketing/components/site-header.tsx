import Link from "next/link";
import { content } from "@/lib/content";
import { siteConfig } from "@/lib/config";

export function SiteHeader() {
  return (
    <header className="site-header">
      <Link className="wordmark" href="/" aria-label={content.nav.homeLink}>
        <span className="wordmark-mark" aria-hidden="true">H</span>
        <span>{content.brandName}</span>
      </Link>
      <nav className="desktop-nav" aria-label={content.nav.mainNavigation}>
        <Link href="/how-it-works/">{content.nav.howItWorks}</Link>
        <Link href="/#for-agents">{content.nav.forAgents}</Link>
        <Link href="/#trust">{content.nav.trust}</Link>
      <Link href="/resources/">{content.nav.resources}</Link></nav>
      <div className="header-actions">
        <a className="sign-in-link" href={siteConfig.appUrl}>{content.nav.signIn}</a>
        <a className="button button-small button-dark" href={siteConfig.signupUrl}>{content.nav.signup}</a>
      </div>
    </header>
  );
}
