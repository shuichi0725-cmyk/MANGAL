import { loadAllManga } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";
import TriageClient from "./TriageClient";

export const metadata = { title: "成年3分けレビュー | MANGAL(テスト専用)", robots: { index: false } };

/** 成年3分けレビューUI(2026-07-07 残タスク着手): adult_us付き作品を人が4状態で確定する。
 *  判定はlocalStorage→「コピー」でJSONを書き出し→Claudeがseed化(adult-overrides)する運用。
 *  テスト専用(previewで使う想定・本番ではリンクを張らない)。 */
export default function AdultTriagePage() {
  const { manga } = loadAllManga();
  const targets = manga
    .filter((m) => (m as unknown as { adult_us?: boolean }).adult_us)
    .map((m) => ({
      slug: m.slug,
      title: m.title,
      authors: (m.authors ?? []).map((a) => a.name).join("・"),
      cover: (() => {
        for (const e of m.editions) for (const v of e.volumes) if (v.cover_url) return v.cover_url;
        return null;
      })(),
      genres: m.genres ?? [],
      demographic: m.demographic,
    }));
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav />
      <TriageClient targets={targets} />
    </div>
  );
}
