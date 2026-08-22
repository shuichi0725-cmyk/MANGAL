import React from "react";

type Props = Omit<React.ImgHTMLAttributes<HTMLImageElement>, "src" | "width" | "height"> & {
  src: string;
  alt?: string;
  width?: number | string;
  height?: number | string;
  fill?: boolean;
  sizes?: string;
  priority?: boolean;
  quality?: number;
  unoptimized?: boolean;
  placeholder?: string;
  blurDataURL?: string;
  loader?: unknown;
};

/**
 * design-sync shim for `next/image`. The real component depends on Next's
 * image optimizer and config; a plain <img> renders the same box. `fill` is
 * reproduced with the absolute-inset style Next itself applies.
 */
export default function Image({
  fill,
  priority,
  quality,
  unoptimized,
  placeholder,
  blurDataURL,
  loader,
  style,
  alt = "",
  ...rest
}: Props) {
  const s: React.CSSProperties = fill
    ? { position: "absolute", inset: 0, width: "100%", height: "100%", ...style }
    : (style ?? {});
  return <img alt={alt} style={s} {...rest} />;
}
