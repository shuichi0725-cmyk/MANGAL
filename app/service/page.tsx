import Link from "next/link";
import type { Metadata } from "next";
import SaleBanner from "@/components/SaleBanner";

/**
 * /service = 漫画好き向けの Amazon サブスク紹介頁(2026-11-24 ユーザ指示「まず /service 頁を作る。
 *   プライムは特典を網羅的にきちんと紹介。他も」)。 作品頁への導線は後(見た目5案は裁定待ち)。
 * ★料金は書かない(改定される= [[feedback_no_static_prices]])。「初回◯日無料」と確認日まで。
 * ★PR表記必須(ステマ規制)。 リンクは各「メンバー紹介プログラム」ヘルプの正式URL+tag。
 *   プライム本体は紹介プログラムがヘルプに無い(2026-11-24 確認)= 通常リンク。
 * ★特典の中身は公式頁を直接読めず(503)解説記事2本の突合で作った = 変わったらここを直す。
 */
const TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG || "mangal08-22";
const LINKS = {
  prime: `https://www.amazon.co.jp/amazonprime?tag=${TAG}`,
  student: `https://www.amazon.co.jp/b?node=2410972051&tag=${TAG}`,
  kindle: `https://www.amazon.co.jp/kindle-dbs/hz/signup?tag=${TAG}`,
  audible: `https://www.amazon.co.jp/b/ref=adbl_JP_as_0068?ie=UTF8&node=7471076051&tag=${TAG}`,
  music: `https://www.amazon.co.jp/music/unlimited/?tag=${TAG}`,
};
const CHECKED = "2026年11月24日";

export const metadata: Metadata = {
  alternates: { canonical: "/service" },
  title: "漫画好きのための Amazon サービス — プライム・Kindle+・Audible・Music Unlimited",
  description:
    "Amazonプライムの特典を配送・Prime Video・Prime Reading・Amazon Photos・セール・家族向けまで一覧で紹介。" +
    "漫画が読み放題の Kindle+(旧 Kindle Unlimited)、原作小説を聴ける Audible、アニメの主題歌を聴ける Music Unlimited も、漫画ファン目線でまとめました。",
};

type Item = [string, string?];

function List({ items }: { items: Item[] }) {
  return (
    <ul>
      {items.map(([b, s]) => (
        <li key={b} className="border-b border-[var(--color-line)]/60 py-2">
          <b className="block text-[14px] text-ink">{b}</b>
          {s && <span className="block text-[12.5px] leading-relaxed text-ink/60">{s}</span>}
        </li>
      ))}
    </ul>
  );
}

function Card({
  id,
  title,
  tag,
  fan,
  children,
  cta,
  href,
  foot,
}: {
  id: string;
  title: string;
  tag: string;
  fan: string;
  children: React.ReactNode;
  cta: string;
  href: string;
  foot?: string;
}) {
  return (
    <section id={id} className="mb-5 border border-[var(--color-line)] border-t-[3px] border-t-[var(--color-accent)] bg-[var(--color-surface)] p-4">
      <h2 className="text-[19px] font-bold text-ink">{title}</h2>
      <p className="mt-0.5 text-[12px] text-[var(--color-accent)]">{tag}</p>
      <p className="my-3 border-l-[3px] border-[var(--color-accent)] bg-[var(--color-accent)]/10 px-2.5 py-2 text-[13px] leading-relaxed text-ink/85">
        <b className="text-[var(--color-accent)]">漫画ファンには:</b> {fan}
      </p>
      {children}
      <a
        href={href}
        target="_blank"
        rel="sponsored noopener"
        className="spring-press mt-4 block bg-[var(--color-accent)] py-3 text-center font-extrabold text-black shadow-[3px_3px_0_rgba(0,0,0,0.45)]"
      >
        {cta}
      </a>
      {foot && <p className="mt-1.5 text-[11.5px] text-ink/55">{foot}</p>}
    </section>
  );
}

function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-1 mt-4 text-[12.5px] font-bold tracking-wider text-ink/55">{children}</h3>;
}

export default function ServicePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 lg:mx-0">
      <p className="text-[11.5px] text-ink/60">
        <span className="mr-1.5 bg-[#ff8a3d] px-1.5 py-px text-[10.5px] font-bold text-black">PR</span>
        このページには Amazon アソシエイトのリンクが含まれます。リンクから登録・購入されると MANGAL に紹介料が入ります。
      </p>
      <h1 className="mt-3 text-2xl font-bold md:text-3xl">漫画好きのための Amazon サービス</h1>
      <p className="mt-1.5 text-sm leading-relaxed text-ink/65">
        アニメ化作品を観る・原作小説を聴く・漫画を読み放題で試す。各サービスの中身を、漫画ファン目線でまとめました。
      </p>

      <SaleBanner className="mt-5" />

      <nav aria-label="サービス" className="mt-5 flex flex-wrap gap-2">
        {[
          ["#prime", "Amazonプライム"],
          ["#kindle", "Kindle+"],
          ["#audible", "Audible"],
          ["#music", "Music Unlimited"],
        ].map(([h, t]) => (
          <a key={h} href={h} className="border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1.5 text-[13px] text-ink">
            <b className="text-[var(--color-accent)]">●</b> {t}
          </a>
        ))}
      </nav>

      <div className="mt-5">
        <Card
          id="prime"
          title="Amazonプライム"
          tag="初回30日間無料体験"
          fan="アニメ化作品を Prime Video で観られる / Prime Reading で対象の漫画(多くは1〜2巻)が読み放題 / 単行本の配送が速く送料無料。"
          cta="プライムを30日間無料で試す"
          href={LINKS.prime}
          foot="特典の中身は変わることがあります。登録前に Amazon の案内で確かめてください。"
        >
          <H3>配送</H3>
          <List
            items={[
              ["配送料無料", "Amazon が発送する商品の通常配送が無料"],
              ["お急ぎ便・当日お急ぎ便・お届け日時指定便が無料", "発売日に届けたい新刊にも"],
              ["特別取扱商品の取扱手数料が無料", "大型・重量物など"],
            ]}
          />
          <H3>観る・聴く・読む</H3>
          <List
            items={[
              ["Prime Video", "対象の映画・ドラマ・アニメが見放題。ダウンロードしてオフラインでも観られる(一部の作品は広告つき。広告なしは追加料金)"],
              [
                "Prime Video のサブスクリプション(旧チャンネル)を追加できる",
                "dアニメストア for Prime Video・アニメタイムズなど、アニメ専門の見放題を Prime Video の中で(別料金・多くは無料体験つき)",
              ],
              ["Amazon Music Prime", "1億曲以上をシャッフル再生で(曲を選んで聴くのは Music Unlimited)"],
              ["Prime Reading", "対象の本・漫画・雑誌が読み放題。同時に10冊まで(対象は入れ替わる。もっと読むなら Kindle+)"],
              ["Amazon Luna(旧 Prime Gaming)", "毎月入れ替わる無料PCゲームを受け取れる(Epic Games Store などで引き換え。日本ではクラウドゲームは対象外)"],
            ]}
          />
          <H3>保存</H3>
          <List items={[["Amazon Photos", "写真を容量無制限で保存(画質そのまま)。家族5人まで共有"]]} />
          <H3>買い物</H3>
          <List
            items={[
              ["会員限定セール", "プライムデー(7月)・プライム感謝祭(10月)"],
              ["タイムセールの先行", "一般より30分早く参加"],
              ["ポイントアップ", "キャンペーン時の上乗せ"],
              ["Amazon Prime Mastercard", "Amazon での買い物の還元率が上がるカードに申し込める"],
            ]}
          />
          <H3>家族・子ども</H3>
          <List
            items={[
              ["家族会員", "同居の家族2人まで、配送特典などを一緒に使える"],
              ["らくらくベビー", "対象のベビー・マタニティ用品が割引"],
              ["定期おトク便のおむつ・おしりふき割引"],
              ["Amazon Kids+ の会員価格", "子ども向けの本・動画・アプリの定額サービスが割安に"],
            ]}
          />
          <details className="mt-3 text-[13px] text-ink/80">
            <summary className="cursor-pointer text-[var(--color-accent)]">学生なら Prime Student(6か月無料体験)</summary>
            <p className="mt-1.5 leading-relaxed">
              大学・大学院・短大・専門学校・高専の学生向け。プライムの主な特典が割安で使え、学生向けの割引もつく(高校生は対象外)。
            </p>
            <a href={LINKS.student} target="_blank" rel="sponsored noopener" className="mt-1 inline-block font-bold text-[var(--color-accent)] underline">
              Prime Student を6か月無料で試す →
            </a>
          </details>
        </Card>

        <Card
          id="kindle"
          title="Kindle+(旧 Kindle Unlimited)"
          tag="初回30日間無料体験 ・ 2026年10月に名前が変わりました(中身は同じ)"
          fan="対象の漫画を1巻から何冊でも。気になっていた作品を試し読み以上に読める。"
          cta="Kindle+ を30日間無料で試す"
          href={LINKS.kindle}
          foot="読み放題の対象は作品・巻ごとに変わります。「この作品が読める」とは限りません。"
        >
          <List
            items={[
              ["数百万冊が読み放題", "漫画・小説・ビジネス書・雑誌(対象は入れ替わる)。プライム付属の Prime Reading より対象がずっと多い"],
              ["同時に20冊まで", "読み終えたら返して次を借りる"],
              ["スマホ・タブレット・PC・Kindle 端末で", "無料の Kindle アプリで読める"],
            ]}
          />
        </Card>

        <Card
          id="audible"
          title="Audible(オーディブル)"
          tag="初回30日間無料体験"
          fan="ライトノベル・Web小説が原作の作品は、原作をプロの朗読で「聴いて」追える。通勤中や家事の間に。"
          cta="Audible を30日間無料で試す"
          href={LINKS.audible}
        >
          <List
            items={[
              ["プレミアムプラン", "対象のオーディオブックが聴き放題。ポッドキャストや Audible オリジナル作品(人気作家の書き下ろし)も"],
              ["スタンダードプラン", "毎月1冊を選んで聴ける"],
              ["再生速度の調整・オフライン再生", "ダウンロードしておけば通信なしで聴ける"],
            ]}
          />
        </Card>

        <Card
          id="music"
          title="Amazon Music Unlimited"
          tag="初回30日間無料体験 ・ プライム会員は割引"
          fan="アニメ化作品の主題歌・劇伴を、曲を選んで何度でも。さらに毎月1冊、原作小説などを Audible で聴ける。"
          cta="Music Unlimited を30日間無料で試す"
          href={LINKS.music}
        >
          <List
            items={[
              ["1億曲以上を曲を選んで再生", "プライム付属の Music Prime はシャッフル再生まで"],
              [
                "Audible のオーディオブックが毎月1冊",
                "90万冊以上から選んで、追加料金なしで Amazon Music アプリで聴ける。選んだ本は翌月以降も聴ける(個人プラン・ファミリープランの持ち主が対象)",
              ],
              ["オフライン再生・高音質(HD・空間オーディオ)"],
              ["プラン", "個人・ファミリー・学生 など"],
            ]}
          />
        </Card>
      </div>

      <p className="mt-2 border-t border-[var(--color-line)] pt-3 text-[12px] leading-relaxed text-ink/60">
        料金は改定されるため、このページには載せていません。最新の料金と条件は各登録ページでご確認ください。 情報の確認日: {CHECKED}。
        <br />
        無料体験は「初めての方」など条件があります。期間中に解約すれば料金はかかりません。
      </p>
      <p className="mt-4 text-sm">
        <Link href="/" className="text-ink/60 hover:text-ink">
          ← トップへ戻る
        </Link>
      </p>
    </div>
  );
}
