import { content } from "@/lib/content";

export type PublicConfigInput = {
  NEXT_PUBLIC_SITE_URL?: string;
  NEXT_PUBLIC_APP_URL?: string;
  NEXT_PUBLIC_PILOT_EMAIL?: string;
};

type PublicConfig = {
  siteUrl: string;
  appUrl: string;
  pilotEmail: string;
};

const developmentDefaults: PublicConfig = {
  siteUrl: "http://localhost:3000",
  appUrl: "http://localhost:3001",
  pilotEmail: "pilot@example.invalid",
};

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === "http:" || url.protocol === "https:") && Boolean(url.hostname);
  } catch {
    return false;
  }
}

function isSaneEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function readValue(
  input: PublicConfigInput,
  key: keyof PublicConfigInput,
  fallback: string,
  validate: (value: string) => boolean,
  kind: string,
  production: boolean,
): string {
  const value = input[key]?.trim();

  if (!value) {
    if (production) {
      throw new Error(`Missing required production configuration: ${key}`);
    }
    return fallback;
  }

  if (!validate(value)) {
    throw new Error(`Invalid ${kind} for ${key}`);
  }

  return value;
}

export function parsePublicConfig(
  input: PublicConfigInput = process.env as PublicConfigInput,
  options: { production?: boolean } = {},
): PublicConfig {
  const production = options.production ?? process.env.NODE_ENV === "production";

  return {
    siteUrl: readValue(input, "NEXT_PUBLIC_SITE_URL", developmentDefaults.siteUrl, isHttpUrl, "URL", production),
    appUrl: readValue(input, "NEXT_PUBLIC_APP_URL", developmentDefaults.appUrl, isHttpUrl, "URL", production),
    pilotEmail: readValue(input, "NEXT_PUBLIC_PILOT_EMAIL", developmentDefaults.pilotEmail, isSaneEmail, "email", production),
  };
}

export const siteConfig = {
  ...parsePublicConfig(),
  indexable: process.env.NEXT_PUBLIC_SITE_INDEXABLE === "true",
} as const;

export function pilotMailto(): string {
  const subject = content.mail.subject;
  const body = [
    content.mail.salutation,
    "",
    content.mail.opening,
    "",
    content.mail.name,
    content.mail.market,
    content.mail.showings,
    "",
    content.mail.closing,
  ].join("\n");

  return `mailto:${siteConfig.pilotEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
