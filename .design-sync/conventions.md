# Building with the MANGAL design system

MANGAL is a Japanese manga catalogue. This library is its presentational layer: 22 components
exported on `window.Mangal`, compiled from the app's own source. They are plain React function
components — **no provider, no theme context, no setup wrapper is required**. Render one and it is
styled.

## The one rule that matters: the class vocabulary is closed

The stylesheet is MANGAL's **compiled Tailwind v4 output**, not Tailwind itself. Only the ~513 class
selectors the app already uses exist in it. A utility MANGAL never wrote — `w-64`, `max-w-lg`,
`text-[10px]`, `gap-7` — is simply absent, and a design that uses one silently renders unstyled.

So, for your own layout glue:

- **Reuse a class you can see in a component's `.prompt.md` example, or in `_ds_bundle.css`.** When in
  doubt, grep it there first.
- **Otherwise use inline `style={{…}}` with the tokens below.** Inline styles always work; invented
  utility classes do not.

Safe, confirmed families (these are in the build): `flex` `grid` `block` `inline-flex`, `items-*`
`justify-*`, `gap-1`–`gap-4`, `p-2`–`p-4` `px-*` `py-*` `mt-*`, `max-w-sm` `max-w-md` `max-w-xl`,
`space-y-2`, `flex-1` `min-w-0` `shrink-0` `truncate` `line-clamp-1`, `text-xs` `text-sm` `text-base`,
`font-medium` `font-semibold` `font-bold`, `w-16` `h-4`–`h-10`, `aspect-[2/3]`, `overflow-hidden`.

## Tokens — the design language

Use these as `var(--…)`; they are defined on `:root` and re-defined per theme.

| Token | Role |
|---|---|
| `--color-ink` / `--color-paper` | text / page ground (warm off-white, faint paper hatch) |
| `--color-surface` / `--color-surface-2` | raised card face / recessed slot |
| `--color-line` | hairline border |
| `--color-accent` | primary red — current page, active chip, buy button |
| `--color-accent-warm` | orange — "連載中" and other in-progress states |
| `--color-on-accent` | text placed on an accent fill (**never hardcode white**) |
| `--radius-card` / `--radius-tag` / `--radius-chip` | 6px / 5px / pill |
| `--shadow-soft` / `--shadow-lift` / `--shadow-press` | rest / hover / active |
| `--font-sans` | system JP stack — no webfont ships, by design |

Ink opacity steps exist only as shipped: `text-ink/15`,`/20`,`/25`,`/30`,`/35`,`/40`,`/45`,`/50`,
`/55`,`/60`,`/65`,`/70`,`/75`, plus `bg-ink` and `bg-ink/80`.

## MANGAL's own classes

- **`tactile`** — the soft-touch surface: face colour, hairline, soft shadow, lift on hover, sink on
  press. This is the core "pressable" primitive; `Card` is built on it.
- **`tactile-chip`** — the same feel at chip scale (`ChipButton`, `Pager` numbers).
- **`mode-recolor`** — recolours a buy button to the active purchase mode (paper vs e-book).
- **`catch-clamp`** — the accent-bordered catch-copy block on a work card.
- **`theme-d3`** — opt-in alternate (dark) palette. It swaps the tokens on its subtree.
  **`CatPict` icons are `display:none` outside `.theme-d3`** — always wrap them in it.
- `cat-svg` / `cat-emoji` / `cat-count`, `d3-marquee`, `d3-blink`, `flip-toggle` / `flip-inner` /
  `flip-face`, `preview-mode` — narrower helpers, used by the components that own them.

## Where the truth is

Read the real files rather than trusting this summary: `_ds/<folder>/styles.css` and the
`_ds_bundle.css` it imports hold every class and token; each component's `<Name>.prompt.md` carries
its props and worked examples.

## An idiomatic composition

```jsx
const { Card, Badge, TagLink } = window.Mangal;

<div className="max-w-md space-y-2">
  <Card href="/manga/berserk" className="flex items-center gap-2 p-3">
    <div className="min-w-0 flex-1">
      <p className="truncate text-sm font-bold">ベルセルク</p>
      <p className="mt-0.5 truncate text-xs text-ink/60">三浦建太郎　1989〜 連載中</p>
    </div>
    <Badge tone="warm">連載中</Badge>
  </Card>

  {/* novel spacing the compiled CSS has no class for → inline style + tokens */}
  <div style={{ display: "flex", gap: 6, paddingBlock: 6 }}>
    <TagLink href="/publisher/hakusensha">白泉社</TagLink>
    <TagLink href="/magazine/young-animal">ヤングアニマル</TagLink>
  </div>
</div>
```

## Notes

- Text is Japanese. Titles can be very long — `truncate` / `line-clamp-1`, or `MarqueeTitle`, which
  scrolls an overflowing title instead of cutting it.
- Covers sit in a `relative … aspect-[2/3]` slot; `CoverImage` renders nothing when its `src` is
  null, so keep the slot's own fallback as a sibling.
- `AffiliateLink` builds store URLs with an **empty** associate tag in design artifacts — links carry
  no tracking id. Do not add one.
