/**
 * design-sync polyfill: `process.env` for the browser bundle.
 *
 * Next.js inlines `process.env.NEXT_PUBLIC_*` at build time; the design-sync
 * bundle is plain esbuild, so the reference survives and throws at module
 * init (VolumeCoverflow and AffiliateLink read it at top level).
 *
 * The values are deliberately EMPTY: these are affiliate/tracking ids, and a
 * design artifact must not carry them. Every consumer already falls back to
 * "" (`?? ""` / `|| ""`), so links render without a tag — which is the
 * correct behaviour for previews.
 *
 * Imported first from ds-entry.tsx so it runs before any component module.
 */
const g = globalThis as unknown as { process?: { env?: Record<string, string> } };

if (!g.process) g.process = { env: {} };
if (!g.process.env) g.process.env = {};

const env = g.process.env;
for (const k of [
  "NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG",
  "NEXT_PUBLIC_AMAZON_LOCALE",
  "NEXT_PUBLIC_RAKUTEN_AFFILIATE_ID",
]) {
  if (env[k] === undefined) env[k] = "";
}

export {};
