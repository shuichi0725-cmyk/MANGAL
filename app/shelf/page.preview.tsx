import type { Metadata } from "next";
import { loadRailMasters } from "@/lib/loadData";
import { preloadListIndex } from "@/lib/preloadIndex";
import MyShelf from "./MyShelf";
// ★見た目の追加は専用CSSへ(Tailwind の新しいクラスは頁にならないファイルからも拾われ、本番の共通CSSを変える)
import "./my-shelf.css";

// ★プレビュー専用(拡張子 .preview.tsx = next.config.ts の pageExtensions が MANGAL_DATA_DIR=.preview-data の時だけ頁にする)。
//   依頼書 = docs/cloud-briefs/my-shelf.md。非索引。
export const metadata: Metadata = {
  title: "本棚(テスト)",
  description: "作品頁の「しまう」で入れた漫画を、もってる/気になる/ほしいの3段の棚に並べる。",
  robots: { index: false, follow: false },
};

/** マイ本棚(/shelf): 中身は端末(ブラウザ)保存+棚のURL。書影・題名・巻数・状態は一覧索引(useMangaIndex)から引く。 */
export default function ShelfPage() {
  preloadListIndex(); // 索引そのものが本文の面 = /list・/browse と同じく HTML の段階で通信を始める
  const genres = loadRailMasters().genres.map((g) => ({ key: g.key, name: g.name }));
  return (
    // ★見た目 C3「黒い棚+真鍮」= docs/cloud-briefs/my-shelf-look-c3.md。サイトの明暗テーマに関係なく常にこの配色
    //   (色は my-shelf.css の .shelf-c3 が、この頁の中だけサイトの色トークンを差し替える)
    <div className="shelf-c3 mx-auto max-w-4xl px-3 pb-12 pt-5">
      <h1 className="text-xl font-extrabold">📚 本棚</h1>
      {/* ★日本語の文は行をまたがない(JSX は改行を空白1つにする=「並びます。 「もってる」」の空白が出る) */}
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink/70">
        作品頁の「しまう」で入れた漫画が、<b>もってる</b>・<b>ほしい</b>・<b>気になる</b>の棚に並びます。
        {"「もってる」は1巻から何巻まで持っているかを覚えていて、続きの巻が出ていれば番号のタイルと札でお知らせします。"}
        {"段を長押し(PCは右クリック)か「⋯」で、棚の移動・巻数の変更・取り出しができます。"}
        {"棚はこの端末だけに保存されるので、頁の下の「棚のURL」を保存しておくと、消えても元に戻せます。"}
      </p>
      <MyShelf genres={genres} />
    </div>
  );
}
