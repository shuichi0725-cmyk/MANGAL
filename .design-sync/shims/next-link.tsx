import React from "react";

type Href = string | { pathname?: string; query?: unknown; hash?: string };

type Props = Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  href: Href;
  prefetch?: boolean | null;
  replace?: boolean;
  scroll?: boolean;
  shallow?: boolean;
  passHref?: boolean;
  legacyBehavior?: boolean;
  locale?: string | false;
};

/**
 * design-sync shim for `next/link`. The real component needs the App Router
 * context, which no preview card has; a plain <a> is the faithful stand-in
 * (same DOM, same classes, same hover/active styling).
 */
export default function Link({
  href,
  prefetch,
  replace,
  scroll,
  shallow,
  passHref,
  legacyBehavior,
  locale,
  children,
  ...rest
}: Props) {
  const to = typeof href === "string" ? href : (href?.pathname ?? "#");
  return (
    <a href={to} {...rest}>
      {children}
    </a>
  );
}
