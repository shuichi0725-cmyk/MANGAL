import { amazonQuerySearchUrls } from "@/lib/amazon";

/**
 * Kindle・Amazon の2つ並びボタン(サーバ/クライアント両用=フックなし)。
 * ★2026-11-09 ユーザ裁定「おすすめで」= 新刊と同じ色・同じ文字を他コーナーにも(見本 v1 の案A・F1・④⑤)。
 *   行き先は羅針盤と同じ「題名 著者」の名前検索(ISBN を持たない = 犬の404を出さない・lib/amazon の注記)。
 *   値段は出さない。 頁の最後に [PR] 表記を置くのは呼び側。
 * - variant "tile" = 3列の升目の下に横幅いっぱい2等分(アニメ化・著者・ジャンル・カラー版)
 * - variant "row"  = 行の中に新刊と同じ大きさで並べる(過去ログ・AI書評家リーグ)
 * - variant "mini" = 詰まった行・見出しの右に小さく(ランキング・全集)
 * - kindleOnly = カラー版(電子だけの本。 紙の Amazon は白黒の通常版に着くので出さない)
 */
const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

export default function BuyButtons({
  title,
  author,
  query,
  variant = "row",
  kindleOnly = false,
  kindleLabel = "Kindle",
  className = "",
}: {
  title: string;
  author?: string | null;
  /** 検索語をそのまま渡す時(既定 = 「題名 著者」) */
  query?: string;
  variant?: "tile" | "row" | "mini";
  kindleOnly?: boolean;
  kindleLabel?: string;
  className?: string;
}) {
  const q = query ?? [title, author].filter(Boolean).join(" ");
  const buy = amazonQuerySearchUrls(q, AMZ_TAG);
  const size =
    variant === "tile"
      ? "h-[22px] flex-1 text-[10px]"
      : variant === "mini"
        ? "h-[18px] px-1.5 text-[9.5px]"
        : "px-2.5 py-0.5 text-[11px]";
  const box = variant === "tile" ? "mt-auto flex gap-[3px] pt-1" : "flex items-center gap-1.5";
  const base = `spring-press inline-flex items-center justify-center whitespace-nowrap font-extrabold text-white ${size}`;
  return (
    <div className={`${box} ${className}`}>
      <a href={buy.kindle} target="_blank" rel="nofollow sponsored noopener" aria-label={`${title} をKindleで探す`} className={`${base} bg-[#3b82f6]`}>
        {kindleLabel}
      </a>
      {!kindleOnly && (
        <a href={buy.paper} target="_blank" rel="nofollow sponsored noopener" aria-label={`${title} をAmazonで探す`} className={`${base} bg-[#e69500]`}>
          Amazon
        </a>
      )}
    </div>
  );
}

/** 頁の最後の [PR] 表記(新刊と同じ文言)。 */
export function BuyPrNote({ className = "" }: { className?: string }) {
  return <p className={`text-[10px] text-ink/40 ${className}`}>[PR] Amazonリンクにはアフィリエイト広告を含みます</p>;
}
