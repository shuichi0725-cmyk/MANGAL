import React from "react";
import { SearchBox } from "mangal";

/** Controlled and empty — placeholder state. */
export function Empty() {
  const [v, setV] = React.useState("");
  return (
    <div className="max-w-md">
      <SearchBox value={v} onChange={setV} />
    </div>
  );
}

/** With a query typed in. */
export function WithQuery() {
  const [v, setV] = React.useState("ベルセルク");
  return (
    <div className="max-w-md">
      <SearchBox value={v} onChange={setV} />
    </div>
  );
}

/** A kana query — the index is searched by reading as well as by title. */
export function KanaQuery() {
  const [v, setV] = React.useState("はんたー");
  return (
    <div className="max-w-md">
      <SearchBox value={v} onChange={setV} />
    </div>
  );
}
