import Link from "next/link";
import { dotGothic } from "@/lib/fonts";
import ShinkanLive from "@/components/ShinkanLive";
import ShinkanMonthNav from "@/components/ShinkanMonthNav";
import ShinkanPageEffects from "@/components/ShinkanPageEffects";
import ShinkanShare from "@/components/ShinkanShare";
import { ShinkanMonthList } from "@/components/ShinkanRow";
import { monthCount, monthSignature, sortedDays, ymLabel, type KnownSet, type ShinkanMonth } from "@/lib/shinkanDates";

/** 1か月分の静的ビュー(server)。/shinkan(今月)・/shinkan/[ym]・/shinkan/next-month が共有(2026-09-01)。
 *  - 本文は build 時に焼く(Googleに見える)。当月以降は ShinkanLive が閲覧時にJSONと突き合わせて鮮度を保つ
 *  - 旧ShinkanClient の体験(共有・年月チップ・日送り・?go=today・?m=互換)は client 小部品で維持 */
export default function ShinkanMonthView({
  ym,
  data,
  months,
  known,
  heading,
  lead,
  pageUrl,
  live,
  prev,
  next,
  notice,
}: {
  ym: string;
  data: ShinkanMonth;
  months: string[];
  known: KnownSet;
  heading: string;
  lead: string;
  pageUrl: string;
  live: boolean;
  prev?: string | null;
  next?: string | null;
  notice?: React.ReactNode;
}) {
  const days = sortedDays(data);
  const n = monthCount(data);
  const list = <ShinkanMonthList ym={ym} data={data} known={known} />;
  // 鮮度差し替え時の「詳細」ゲート用: build 時点で索引に居た slug(当月分だけ・重複除去)
  const knownSlugs = [...new Set([...days.flatMap((d) => data.days[d]), ...(data.unknown ?? [])].map((it) => it[0]).filter((s) => known.has(s)))];
  return (
    <div className="mx-auto w-full max-w-[720px] pb-12">
      <header className="border-b-[3px] border-[var(--color-accent)] px-4 py-3">
        <div className="flex items-center gap-2">
          <h1 className={`${dotGothic.className} text-[22px] font-black`}>📦 {heading}</h1>
          {n > 0 && (
            <span className="border border-[var(--color-line)] px-2 py-0.5 text-[12px] font-black text-ink/75">
              全{n.toLocaleString()}冊
            </span>
          )}
          <ShinkanShare url={pageUrl} text={`${ymLabel(ym)}の漫画新刊 ${n.toLocaleString()}冊一覧 | MANGAL`} />
        </div>
        <p className="mt-0.5 text-[11px] text-ink/55">{lead}</p>
        <ShinkanMonthNav months={months} current={ym} />
        {(prev || next) && (
          <nav className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] font-bold" aria-label="前後の月">
            {prev ? <Link href={`/shinkan/${prev}`} className="underline">← {ymLabel(prev)}</Link> : <span className="text-ink/35">← 前の月</span>}
            {next ? <Link href={`/shinkan/${next}`} className="underline">{ymLabel(next)} →</Link> : <span className="text-ink/35">次の月 →</span>}
          </nav>
        )}
        {days.length > 0 && (
          <p className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-[11px]" aria-label="日付へ移動">
            {days.map((day) => (
              <a key={day} href={`#day-${Number(day)}`} className="underline text-ink/70">
                {Number(day)}日({data.days[day].length})
              </a>
            ))}
          </p>
        )}
      </header>
      {notice}
      <ShinkanPageEffects ym={ym} days={days.map(Number)} />
      {live ? (
        <ShinkanLive ym={ym} sig={monthSignature(data)} knownSlugs={knownSlugs}>
          {list}
        </ShinkanLive>
      ) : (
        list
      )}
    </div>
  );
}
