import { loadAllManga } from "@/lib/loadData";
import HomeClient from "./HomeClient";

export default function HomePage() {
  const data = loadAllManga();
  return <HomeClient data={data} />;
}
