import type { Edition, Manga } from "@/lib/schema";

/** ★巻明細のSSR化パイロット (2026-09-16 ユーザ指示「テスト環境のうる星やつらだけ」)。
 *
 *  背景: 巻の詳細(発売日/ISBN/出版社)は VolumeCoverflow が **選択中の1巻しか描画しない**
 *  ため、静的HTMLに載るのは第1巻ぶんだけだった(実測: ちいかわ頁で「発売」2回・「ISBN」1回)。
 *  クリックで初めて出る内容はGoogleがインデックスしないので、「作品名 N巻 発売日」系の
 *  巻単位ロングテールに構造上1件も当たれない。
 *
 *  ここでは**軽量なテキスト明細だけ**を server component で出す(リンク・画像を持たない)。
 *  詳細パネルごと全巻複製する案は、試し読み/特装版のアフィリンクと大書影が巻数倍に増えるので採らない。
 *
 *  ★対象slugは下の SEO_VOLUME_LIST_SLUGS だけ。全展開はユーザGO待ち。 */
export const SEO_VOLUME_LIST_SLUGS = new Set<string>(["urusei-yatsura"]);

function fmtDateJa(d?: string | null): string {
  const s = d ? String(d) : "";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (m) return `${m[1]}年${Number(m[2])}月${Number(m[3])}日発売`;
  const ym = /^(\d{4})-(\d{2})$/.exec(s);
  if (ym) return `${ym[1]}年${Number(ym[2])}月発売`;
  return s ? `${s}発売` : "";
}

function fmtIsbn(v?: string | number | null): string {
  const s = v == null ? "" : String(v);
  if (s.length === 13) return `${s.slice(0, 3)}-${s.slice(3, 4)}-${s.slice(4, 6)}-${s.slice(6, 12)}-${s.slice(12)}`;
  return s;
}

/** 版 → 表示用ブロック。 刷(versions)を持つ版は刷ごとに分ける(VolumeRow の表示と揃える)。 */
function blocks(editions: Edition[]): { label: string; publisher?: string | null; volumes: Edition["volumes"] }[] {
  const out: { label: string; publisher?: string | null; volumes: Edition["volumes"] }[] = [];
  for (const ed of editions) {
    if (ed.versions && ed.versions.length > 1) {
      for (const v of ed.versions) out.push({ label: `${ed.label} ${v.label}`, publisher: ed.publisher, volumes: v.volumes });
    } else {
      out.push({ label: ed.label, publisher: ed.publisher, volumes: ed.volumes });
    }
  }
  return out;
}

export default function VolumeSeoList({ manga }: { manga: Manga }) {
  if (!SEO_VOLUME_LIST_SLUGS.has(manga.slug)) return null;
  const bs = blocks(manga.editions).filter((b) => b.volumes.length > 0);
  if (!bs.length) return null;

  return (
    <section className="mt-6">
      <h2 className="text-[15px] font-bold">全巻リスト（発売日・ISBN）</h2>
      <p className="mt-1 text-[11px] text-ink/45">
        {manga.title} の各巻の発売日とISBNの一覧です。
      </p>
      {bs.map((b, i) => (
        <div key={i} className="mt-3">
          <h3 className="text-[13px] font-bold text-ink/75">
            {b.label}
            <span className="ml-2 text-[11px] font-normal text-ink/45">全{b.volumes.length}巻</span>
          </h3>
          <ul className="mt-1.5 divide-y divide-[var(--color-line)] rounded-xl border border-[var(--color-line)]">
            {b.volumes.map((v, j) => {
              const label = v.volume_label ?? (v.number != null ? `第${v.number}巻` : "");
              const date = fmtDateJa(v.release_date);
              const isbn = fmtIsbn(v.isbn13);
              const pub = v.publisher ?? b.publisher ?? manga.publisher;
              return (
                <li key={j} className="px-3 py-2 text-[12px] leading-relaxed">
                  <span className="font-semibold">{manga.title} {label}</span>
                  {v.title_display && <span className="text-ink/60">（{v.title_display}）</span>}
                  {date && <span className="text-ink/70"> — {date}</span>}
                  {isbn && <span className="text-ink/55"> / ISBN {isbn}</span>}
                  {pub && <span className="text-ink/55"> / {pub}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </section>
  );
}
