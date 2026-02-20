/**
 * Shared legal/brand constants for Terms, Privacy, Refunds, Contact, and Pricing.
 * Used for Paddle website approval and consistent legal copy.
 */

export const PRODUCT_NAME = 'JobScoutAI';
export const BRAND_NAME = 'JobScoutAI';
// Must match the legal business name submitted to Paddle.
export const OPERATOR_LEGAL_NAME = 'AetherFlow Technologies Inc.';
export const WEBSITE_URL = 'https://jobscoutai.vercel.app';
export const GOVERNING_LAW = 'Pakistan';

/** Support email; override via NEXT_PUBLIC_SUPPORT_EMAIL in production. */
export const SUPPORT_EMAIL =
  typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_SUPPORT_EMAIL
    ? process.env.NEXT_PUBLIC_SUPPORT_EMAIL
    : 'support@jobscoutai.com';

/** Do not invent a phone number; omit if not in use. */
export const SUPPORT_PHONE: string | undefined = undefined;

/** Last updated date for Terms, Privacy, Refunds (YYYY-MM-DD). Update when you change those pages. */
export const lastUpdatedISO = '2026-02-20';
