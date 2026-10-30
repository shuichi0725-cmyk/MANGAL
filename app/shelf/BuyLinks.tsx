import { amazonQuerySearchUrls } from "@/lib/amazon";

const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

/**
 * 本棚から Kindle・Amazon へその場で飛ぶ2つのボタン(2026-10-31 ユーザ要望「持っていない巻・ほしい/気になるを、その場でアマゾン、キンドルへ」)。
 * ★羅針盤・作品頁と同じ規則 = 名前で探す(「題名 N巻 著者」)。 ISBN の /dp/ は紙の頁が無い巻で犬の404になる
 *   (2026-10-15 ユーザ裁定「ブラウザで開くよりエラーを出さない方を優先」= lib/amazon の注記)。 価格は書かない。
 * ★段(作品頁へのリンク)の中に置かない = a の入れ子になる。 呼び側は Link の外に置く。
 */
export default function BuyLinks({
  title,
  author,
  n,
  label,
}: {
  title: string;
  author?: string | null;
  /** 巻番号(無ければ作品名で探す) */
  n?: number;
  /** ボタンの前に出す札(例「6巻」) */
  label?: string;
}) {
  const buy = amazonQuerySearchUrls([title, n ? `${n}巻` : "", author ?? ""].filter(Boolean).join(" "), AMZ_TAG);
  const what = n ? `${title} ${n}巻` : title;
  return (
    <span className="shelf-buy">
      {label && <span className="shelf-buy-label">{label}</span>}
      <a className="shelf-buy-btn is-k" href={buy.kindle} target="_blank" rel="noopener nofollow sponsored" aria-label={`${what} をKindleで探す`}>
        Kindle
      </a>
      <a className="shelf-buy-btn is-a" href={buy.paper} target="_blank" rel="noopener nofollow sponsored" aria-label={`${what} をAmazon(紙)で探す`}>
        Amazon
      </a>
    </span>
  );
}
