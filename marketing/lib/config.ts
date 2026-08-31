export type PublicConfigInput = {
  NEXT_PUBLIC_SITE_URL?: string;
  NEXT_PUBLIC_APP_URL?: string;
  NEXT_PUBLIC_CONTACT_EMAIL?: string;
};

type PublicConfig = {
  siteUrl: string;
  appUrl: string;
  contactEmail: string;
};

const developmentDefaults: PublicConfig = {
  siteUrl: "http://localhost:3000",
  appUrl: "http://localhost:3001",
  contactEmail: "contact@example.invalid",
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
    contactEmail: readValue(input, "NEXT_PUBLIC_CONTACT_EMAIL", developmentDefaults.contactEmail, isSaneEmail, "email", production),
  };
}

const publicConfig = parsePublicConfig();

export const siteConfig = {
  ...publicConfig,
  signupUrl: new URL("/signup", publicConfig.appUrl).toString(),
  indexable: process.env.NEXT_PUBLIC_SITE_INDEXABLE === "true",
} as const;

export function contactMailto(): string {
  return `mailto:${siteConfig.contactEmail}`;
}
