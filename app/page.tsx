import { Suspense } from "react";
import { loadAllManga } from "@/lib/loadData";
import HomeClient from "./HomeClient";

export default function HomePage() {
  const data = loadAllManga();
  return (
    <Suspense fallback={null}>
      <HomeClient data={data} />
    </Suspense>
  );
}
