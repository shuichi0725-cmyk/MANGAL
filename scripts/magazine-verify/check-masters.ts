// 雑誌マスタ等を next build と同じローダで読む(zod 検査込み)。 MANGAL_DATA_DIR=.preview-data で preview、 未指定で本番 data/。
import { loadMasters, loadAllManga } from "../../lib/loadData";
const m = loadMasters();
console.log("masters OK: magazines", m.magazines.length, "publishers", m.publishers.length);
if (process.env.FULL) {
  const b = loadAllManga();
  console.log("loadAllManga OK: manga", b.manga.length);
}
