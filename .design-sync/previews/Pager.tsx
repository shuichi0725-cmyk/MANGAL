import React from "react";
import { Pager } from "mangal";

/** Long result set, page 1 — trailing ellipsis only. */
export function FirstPage() {
  const [page, setPage] = React.useState(1);
  return <Pager page={page} totalPages={42} onChange={setPage} />;
}

/** Mid-run — ellipsis on both sides, current page filled with the accent. */
export function MiddlePage() {
  const [page, setPage] = React.useState(17);
  return <Pager page={page} totalPages={42} onChange={setPage} />;
}

/** Last page — the "next" control is disabled. */
export function LastPage() {
  const [page, setPage] = React.useState(42);
  return <Pager page={page} totalPages={42} onChange={setPage} />;
}

/** Seven pages or fewer: every number is listed, no ellipsis. */
export function ShortRun() {
  const [page, setPage] = React.useState(3);
  return <Pager page={page} totalPages={6} onChange={setPage} />;
}
