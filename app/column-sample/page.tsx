import Link from "next/link";
import { DesignNav } from "@/lib/homeDesign";

/** 週刊コラム(モック1本)。 本実装 = AI月次バッチ生成(ネタバレ検査パス付)→seed→静的生成。
 *  完結作限定・ネタバレなし・読み応え重視の長文。 */
export default function ColumnSample() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-16">
      <DesignNav current={11} />
      <article className="mx-auto max-w-xl px-5 pt-8">
        <p className="text-[10px] font-bold tracking-[0.25em] text-[var(--color-accent)]">週刊コラム ・ 完結作だけ、ネタバレなし</p>
        <h1 className="mt-2 text-[22px] font-black leading-snug">
          「強さ」を測る漫画が、「正しさ」を疑い始めるまで——『幽☆遊☆白書』を今読む理由
        </h1>
        <p className="mt-2 text-[11px] text-ink/50">2026.06.12 ・ 読了目安 5分 ・ 担当: タケル(元書店員)</p>

        <div className="mt-6 space-y-5 text-[14px] leading-[1.95] text-ink/85">
          <p>
            主人公が冒頭で死ぬ少年漫画は、当時ほとんど存在しなかった。1990年に週刊少年ジャンプで始まった『幽☆遊☆白書』は、不良少年・浦飯幽助が子どもを庇って車にはねられるところから始まる。しかも霊界の側が「君が死ぬ予定は無かった。手違いだ」と告げる。この出だしの異様さは、34年経った今読み返しても色褪せない。物語の根っこに「世界の采配は案外いい加減である」という諦観が最初から埋め込まれているからだ。
          </p>
          <p>
            序盤は一話完結の人情譚が続く。死んだ幽助が幽霊として街を見回り、生き返るための試練をこなす——ここだけ読むと心温まる霊界奇譚で、実際この時期の本作は涙腺に来る短編の宝庫だ。だが本作の本領は、生き返った幽助が「霊界探偵」となり、妖怪がらみの事件を追い始めてから徐々に立ち上がる。腕力の物語に転じたのではない。<b>「強さとは何か」を測るための舞台</b>が、慎重に組み上がっていくのだ。
          </p>
          <p>
            中盤の武術大会編は、トーナメント漫画の教科書として今なお引用され続けている。だが本作のトーナメントが特別なのは、勝敗の演出ではなく「強い奴ほど、何かを背負っている」という描き方の徹底にある。敵側の妖怪にすら一人ずつ来歴があり、倒された者の矜持が観客の野次より長く記憶に残る。とりわけ幽助の宿敵となる、ある孤高の戦士の造形は、後年のあらゆる「クールなライバル像」の原型のひとつと言っていい。
          </p>
          <p>
            そして本作は、終盤に向かうにつれて少年漫画の約束事そのものを疑い始める。「悪い妖怪を倒す正義の人間」という前提が、ある事件をきっかけに足元から揺らぐのだ。人間とは守るに値する種なのか。正義を信じ切れなくなった者は、どこへ向かえばいいのか。週刊少年誌の真ん中で、作者・冨樫義博はこの問いを真正面から少年読者に投げた。その誠実さと危うさは、今の漫画でもなかなかお目にかかれない。
          </p>
          <p>
            全19巻(完全版は15巻)。長すぎず、しかし駆け足でもない。そして完結している——つまり、今夜読み始めたあなたは、宙吊りのまま何年も待たされる心配なく、この物語の最後の一行まで辿り着ける。圧倒的な画力の進化を眺めるもよし、90年代ジャンプの空気を吸うもよし。ただ個人的には、読み終えたあとに「強さって何だったんだろう」と少しだけ考え込んでしまう、あの静かな余韻のために薦めたい。
          </p>
        </div>

        <div className="mt-8 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4">
          <p className="text-[11px] text-ink/55">この作品のページへ</p>
          <Link href="/manga/yu-yu-hakusho" className="spring-press mt-1 block text-[15px] font-bold text-[var(--color-accent)]">
            幽☆遊☆白書(冨樫義博・全19巻・完結) →
          </Link>
        </div>

        <div className="mt-6 flex items-center justify-between text-[11px] text-ink/50">
          <span className="spring-press">← 先週: 『あずまんが大王』</span>
          <Link href="/sansedai-archive" className="spring-press">コラム一覧 →</Link>
        </div>
      </article>
    </div>
  );
}
