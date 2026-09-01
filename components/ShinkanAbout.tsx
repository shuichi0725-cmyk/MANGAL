import Link from "next/link";

/** 新刊発売日ページ共通の解説(2026-09-01 SEO: 出典・更新頻度・予約の説明=E-E-A-Tと語の露出)。 */
export default function ShinkanAbout() {
  return (
    <section className="mx-auto mt-8 w-full max-w-[720px] border-t border-[var(--color-line)] px-4 py-5 text-[12.5px] leading-relaxed text-ink/70">
      <h2 className="mb-2 text-[14px] font-black text-ink/85">漫画・コミックの新刊発売日について</h2>
      <p>
        このページは、日本で出版される漫画・コミックの新刊を<strong>発売日ごとに全冊</strong>並べた一覧です。
        発売日と書誌(巻数・ISBN・出版社・レーベル)は文化庁メディア芸術データベース・国立国会図書館サーチ・楽天ブックスの情報をもとに作成し、
        <strong>毎週更新</strong>しています。発売前の巻は出版社の発表・予約情報を反映した<strong>発売予定日</strong>で、地域や店舗によって店頭に並ぶ日が前後することがあります。
      </p>
      <p className="mt-2">
        書影または題名から Amazon で予約・購入でき、「詳細」からは作品ページ(全巻の発売日・あらすじ・関連作)へ移動できます。
        月をまたいで探すときは各月のページ、直近だけ見たいときは <Link href="/shinkan/this-week" className="underline">今週の新刊</Link> と{" "}
        <Link href="/shinkan/next-month" className="underline">来月の新刊</Link> をどうぞ。作品名がわかっているときは{" "}
        <Link href="/browse" className="underline">検索</Link> から作品ページの発売日一覧が早いです。
      </p>
    </section>
  );
}
