import Link from "next/link";
import type { AiReviewSection } from "@/lib/loadData";
import { characterFor, type AiCharacter } from "@/lib/aiCharacters";

/** AIキャラのアバター(飾り)。 スプライト(img)があれば絵、 無ければ emoji フォールバック。
 *  ★ブランド名は名乗らせない=飾りのみ。 実名は別途テキストで表示([[ai_review_league_operation]])。 */
function Avatar({ c, size = 40 }: { c: AiCharacter; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-xl border shadow-sm"
      style={{
        width: size,
        height: size,
        backgroundColor: c.tint,
        borderColor: c.color,
        fontSize: Math.round(size * 0.52),
        lineHeight: 1,
      }}
    >
      {c.img ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={c.img} alt="" width={size} height={size} style={{ imageRendering: "pixelated" }} />
      ) : (
        c.face
      )}
    </span>
  );
}

/** AI書評家リーグの1節を描画(課題図書+共通プロンプト+各社AIの書評を並べる)。
 *  /column-ai-league(最新節) と /column-ai-league/[setsu](過去ログ) で共用。 */
export default function AiReviewSectionView({ section }: { section: AiReviewSection }) {
  const chars = section.reviews.map((r) => characterFor(r.vendor));
  return (
    <div>
      <p className="text-[10px] font-bold tracking-[0.25em] text-[var(--color-accent)]">
        AI書評家リーグ ・ 第{section.setsu - 1}節
      </p>
      <h1 className="mt-2 text-[22px] font-black leading-snug">
        今回の課題図書『{section.title}』を、<br />AI書評家{section.reviews.length}人が読んだら。
      </h1>
      <p className="mt-3 text-[12.5px] leading-relaxed text-ink/70">
        同じ本、同じ依頼文。それでも書評はこんなに違う——複数のAIに全く同じお題を渡し、出てきた紹介文をそのまま並べました（ネタバレなし・完結作限定）。
      </p>

      {/* 出演AI = キャラのラインナップ(飾り。 顔で誰の評か掴みやすく) */}
      <div className="mt-4 flex items-center gap-2 overflow-x-auto rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2.5">
        <span className="shrink-0 text-[10px] font-bold text-ink/45">出演</span>
        {chars.map((c, i) => (
          <Avatar key={i} c={c} size={34} />
        ))}
      </div>

      <details className="mt-3 rounded-lg border border-dashed border-[var(--color-line)] p-3 text-[11px] text-ink/60">
        <summary className="spring-press cursor-pointer font-semibold">全員に渡した依頼文（共通）</summary>
        <p className="mt-2 leading-relaxed">{section.prompt}</p>
      </details>

      <div className="mt-6 space-y-6">
        {section.reviews.map((r, i) => (
          <article
            key={`${r.vendor}-${r.model}-${i}`}
            className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4 shadow-sm"
          >
            <div className="flex items-center gap-3 border-b border-[var(--color-line)] pb-2.5">
              <Avatar c={chars[i]} size={40} />
              <p className="text-[15px] font-extrabold">
                {r.model} <span className="text-[10px] font-semibold text-ink/45">（{r.vendor}）</span>
              </p>
            </div>
            <div className="mt-3 space-y-3 text-[13px] leading-[1.9] text-ink/85">
              {r.text.split("\n").map((p, j) => (
                <p key={j}>{p}</p>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4">
        <p className="text-[11px] text-ink/55">課題図書のページへ</p>
        <Link
          href={`/manga/${section.slug}`}
          className="spring-press mt-1 block text-[15px] font-bold text-[var(--color-accent)]"
        >
          {section.title}（{section.author}・完結） →
        </Link>
      </div>
      <p className="mt-4 text-center text-[10px] leading-relaxed text-ink/40">
        各書評は各AIサービスの出力をそのまま掲載（生成AI明記・無加工）。<br />
        キャラクターはイメージです。各AI企業・公式とは一切関係ありません。
      </p>
    </div>
  );
}
