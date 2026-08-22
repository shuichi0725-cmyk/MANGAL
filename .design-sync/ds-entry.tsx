/**
 * design-sync bundle entry for the MANGAL design system.
 *
 * The repo is a Next.js app, not a published component package: its components
 * are default exports and there is no `dist/`. This barrel re-exports the
 * portable, presentational subset under named exports so the converter can
 * bundle them onto `window.Mangal`. It adds no behaviour — every component
 * below is the repo's own source, untouched.
 */

// Must be first: defines process.env before any component module reads it.
import "./shims/process-env";

// ── primitives (components/ui)
export { default as Badge } from "@/components/ui/Badge";
export { default as Card } from "@/components/ui/Card";
export { ChipButton, ChipLink, TagLink } from "@/components/ui/Chip";
export { default as Pager } from "@/components/ui/Pager";

// ── presentational
export { default as CatPict } from "@/components/CatPict";
export { default as MarqueeTitle } from "@/components/MarqueeTitle";
export { default as CoverImage } from "@/components/CoverImage";
export { default as ColorEditionNote } from "@/components/ColorEditionNote";
export { default as CoverLightbox } from "@/components/CoverLightbox";
export { default as LikeButton } from "@/components/LikeButton";
export { default as LikeButtonMock } from "@/components/LikeButtonMock";
export { default as ScrollTopButton } from "@/components/ScrollTopButton";
export { default as SearchBox } from "@/components/SearchBox";
export { default as ShareButtons } from "@/components/ShareButtons";

// ── catalogue surfaces (schema/format only — no data loaders)
export { default as MangaCard } from "@/components/MangaCard";
export { default as MangaGrid } from "@/components/MangaGrid";
export { default as VolumeTile } from "@/components/VolumeTile";
export { default as ArtBookCard } from "@/components/ArtBookCard";
export { default as EditionVolumes } from "@/components/EditionVolumes";
export { default as AffiliateLink } from "@/components/AffiliateLink";
