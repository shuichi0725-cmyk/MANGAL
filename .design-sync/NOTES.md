# design-sync notes — MANGAL

## What this repo is (and why the config looks unusual)

MANGAL is a **Next.js application, not a published component package**: `package.json` is
`private: true` with no `main`/`module`/`exports`, there is no `dist/`, no Storybook, and every
component is a **default** export of a local `.tsx`. The converter's normal package path (bundle the
shipped `dist/`, read props from the shipped `.d.ts` tree) has nothing to work with here, so this
sync supplies the three missing pieces itself:

- **`.design-sync/ds-entry.tsx`** — a barrel that re-exports the portable subset under *named*
  exports. This is the `--entry`. It adds no behaviour; every component is the repo's own source.
  ★ **Adding a component to the sync = adding a line here AND an entry in `cfg.componentSrcMap`.**
  (`export *` in a synthesised entry would export nothing — these are default exports.)
- **`.design-sync/tsconfig.sync.json`** — resolves `@/*` and swaps `next/link` / `next/image` for the
  shims in `.design-sync/shims/`. The real Next components need App Router context that no preview
  card has; the shims render the same DOM (`<a>` / `<img>`, `fill` reproduced as absolute inset).
- **`.design-sync/shims/process-env.ts`** — `VolumeCoverflow` and `AffiliateLink` read
  `process.env.NEXT_PUBLIC_*` at module scope. Next inlines those at build time; esbuild does not, so
  without this the bundle throws `process is not defined` at init and `window.Mangal` never gets
  assigned. ★ **It must stay the first import in `ds-entry.tsx`.** Values are deliberately empty —
  affiliate/tracking ids must not ship in design artifacts.

## Command

```sh
node .ds-sync/resync.mjs --config .design-sync/config.json --node-modules ./node_modules \
  --entry ./.design-sync/ds-entry.tsx --out ./ds-bundle [--remote .design-sync/.cache/remote-sync.json]
```

No `buildCmd`: nothing needs building first — except the CSS, see the risk below.

## Config decisions

- **`srcDir: "components"`** is required. The default probe order is `src` → `lib` → `components`,
  and this repo has a `lib/` (data loaders) that would win and yield no component matches.
- **`cssEntry` = `out/_next/static/css/2bebe2671023ca37.css`** — the app's own compiled Tailwind v4
  output, which carries the `:root` tokens and MANGAL's custom classes. See risks.
- **`guidelinesGlob: []`** on purpose. The default globs swept 26 files out of `docs/`, which are
  MANGAL's *data-pipeline* documents (ISBN merges, MADB probes, deploy runbooks) — nothing to do with
  UI. Shipping them as "design guidelines" would mislead the design agent.
- **`extraFonts` deliberately unset.** `out/_next/static/css/9a86d1bdc7c4f7d9.css` holds 123
  `@font-face` rules for **DotGothic16** (1.2 MB of subsets), but that family is used only by
  `app/home-design-12/HeroD3.tsx` and is referenced by neither the shipped stylesheet nor any synced
  component. Wiring it produced `[FONT_DANGLING]` (its `url()`s are site-absolute) for zero benefit.
- **`dtsPropsFor` is hand-written for all 22.** Auto-extraction produced `[key: string]: unknown` for
  every component because the props are **unexported local `type Props`**. The `.d.ts` is the design
  agent's API contract, so these are maintained by hand. ★ **Changing a component's props means
  updating `dtsPropsFor` — nothing checks this automatically.**
- **`overrides.cardMode: "column"`** on the five wide catalogue surfaces (MangaCard, MangaGrid,
  ArtBookCard, VolumeTile, EditionVolumes) so they don't clip in the multi-column card grid.

## Scope: 22 of 57 components

Included: the `components/ui/` primitives, the purely presentational components, and the catalogue
surfaces that depend only on `lib/schema.ts` (zod types) and `lib/format.ts` (pure functions).

Excluded, with reasons — re-check these before widening scope:

- `VolumeRow` — imports `lib/tameshiyomi`, which imports `node:fs`.
- `ListClient`, `HomeSidebar`, `CategoryHub`, `TokushuClient` — `next/navigation` router hooks.
- `AnimeSeasonCorner`, `ZenshuuCorner` — import `@/data/*.json` read at build time.
- Everything else importing `@/lib/loadData` or `@/lib/useMangaIndex`.
- `PurchaseModeProvider` / `PurchaseModeToggle` / `usePurchaseMode` — a context trio. Not needed for
  `AffiliateLink`: `usePurchaseMode` returns a safe `{ mode: "print" }` default outside the provider,
  so **no `cfg.provider` is required anywhere in this DS**. Syncing the toggle would mean wrapping
  every card in the provider; deferred.

## Known render warns (triaged — a warn *not* listed here is new)

- **`[FONT_MISSING]` "BIZ UDPGothic", "Yu Gothic UI", "Cambria"** — not a missing brand font. These
  are entries in the `--font-sans` / `--font-serif` **system** stacks; MANGAL ships no webfont by
  design, so there is no file to wire. Expected on every run.

## Floor cards (2 of 22 — intentional, not failures)

- **`ScrollTopButton`** — visibility is driven by `window.scrollY > 400`; it cannot render in a static
  card. No props, nothing to show.
- **`ColorEditionNote`** — fetches `/data/color-editions.json` at runtime, which no preview host
  serves, so it renders `null`. An authored preview was written, reviewed, and **removed** because it
  showed only its own scaffolding. Do not re-add one without a way to seed that data.

## The finding that shaped the conventions header

The shipped stylesheet is MANGAL's **compiled** Tailwind v4 output — a closed set of ~513 class
selectors. Utilities the app never wrote (`w-64`, `max-w-lg`, `text-[10px]`) do not exist and render
as nothing. This bit the first pass of the `MarqueeTitle` / `TagLink` / `CatPict` previews. Preview
and design layout glue must reuse shipped classes or fall back to inline `style` + `var(--token)`.
Also: **`CatPict` icons are `display:none` outside `.theme-d3`** — always wrap them.

## Re-sync risks

1. ★ **`cssEntry` is a hashed build artifact.** `out/_next/static/css/<hash>.css` gets a **new
   filename on every `next build`**. When the app is rebuilt, this path goes stale and the build
   fails or ships old CSS. **Check it first on any re-sync**: `ls out/_next/static/css/` and pick the
   file containing `.tactile` (the other one is the DotGothic16 `@font-face` sheet). A durable fix
   would be a small script that resolves it at build time.
2. **`out/` must exist.** It is a build output, not source. On a fresh clone there is no compiled CSS
   until someone runs the site build.
3. **`dtsPropsFor` mirrors the source by hand.** Prop changes in `components/*.tsx` will not surface
   as an error — the emitted contract just goes quietly wrong.
4. **Previews inline realistic literal data.** They are typed loosely on purpose (esbuild strips
   types, so shape drift in `lib/schema.ts` will not fail the build — it will surface as a preview
   that renders oddly).
5. **Groups are all `general`.** The converter treats `ui` as a generic container name, so
   `components/ui/*` does not become its own group. Regrouping needs `cfg.docsMap` stubs; not done
   because a frontmatter-only stub replaces the synthesized `.prompt.md` body, and the API contract
   matters more than the grouping.
6. **Only `next/link` and `next/image` are shimmed.** Adding a component that touches any other Next
   runtime API needs a new shim plus a `paths` entry.
