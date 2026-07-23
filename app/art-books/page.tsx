import Link from "next/link";
import ArtBookCard from "@/components/ArtBookCard";
import { loadArtBooks } from "@/lib/loadData";

export const metadata = {
  title: "画集",
  description:
    "漫画家の画集・原画集・イラスト集の一覧。作画家・出版社・出版年と購入リンクつき。",
  alternates: { canonical: "/art-books" },
};

/**
 * 画集一覧 (= /art-books のランディング)。
 * ★これまで画集一覧は「ホームの ?artBooks=true モード」だけにあり、 メニュー/フッタが
 *   指す /art-books 直下に index ページが無く 404 になっていた (個別 /art-books/[slug] は存在)。
 * ★静的な全件グリッド (203件程度と少量なので全描画で十分)。 検索・出版年フィルタは
 *   既存の絞り込みビュー (/browse?artBooks=true) へ誘導する。
 */
export default function ArtBooksIndexPage() {
  const artBooks = loadArtBooks();
  // 50音順 (= 名前昇順。 サイト共通の名前ソート軸)。
  const sorted = [...artBooks].sort((a, b) =>
    a.title_kana.localeCompare(b.title_kana, "ja"),
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <header className="border-b border-[var(--color-line)] pb-5">
        <h1 className="text-2xl md:text-3xl font-bold flex items-center gap-2">
          <span aria-hidden="true">🎨</span> 画集
        </h1>
        <p className="mt-2 text-sm text-ink/60 max-w-2xl">
          漫画家の画集・原画集・イラスト集。 作画家・出版社・出版年と購入リンクつき。
        </p>
        <div className="mt-3 flex items-center gap-3 flex-wrap text-sm">
          <span className="text-ink/55">全 {artBooks.length} 冊</span>
          <Link
            href="/browse?artBooks=true"
            className="inline-flex items-center rounded-[var(--radius-tag)] border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5 font-medium text-ink/85 transition duration-100 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] active:scale-[0.96]"
          >
            🔍 作画家・出版年で絞り込む
          </Link>
        </div>
      </header>

      {sorted.length === 0 ? (
        <div className="mt-16 text-center text-ink/45">
          <p className="text-3xl" aria-hidden="true">🎨</p>
          <p className="mt-3 text-sm">画集データを準備中です。</p>
        </div>
      ) : (
        <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {sorted.map((a) => (
            <li key={a.slug}>
              <ArtBookCard artBook={a} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
