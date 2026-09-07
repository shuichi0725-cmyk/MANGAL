import AizoubanListClient from "./AizoubanListClient";

/** 愛蔵版・合本の一覧(2026-09-06 新設。ホームの📚コーナーの「全部見る」先)。
 *  データ=public/data/aizouban-stock.json(_gen-corner-auto.py が週次再生成)。
 *  クライアントfetch方式なのでJSON差し替えだけで一覧も追随する(/color-manga と同型)。 */
export const metadata = {
  alternates: { canonical: "/aizouban" },
  title: "愛蔵版・完全版・合本で読める漫画",
  description:
    "全巻が少ない冊数にまとまった愛蔵版・完全版・ワイド版・新装版の一覧。「全31巻→24巻」のように、通常版より冊数が減っている版だけを集めました。",
};

export default function AizoubanPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="px-4 pb-2 pt-6">
        <h1 className="text-[19px] font-extrabold">📚 愛蔵版・合本で読める漫画</h1>
        <p className="mt-1 text-[12px] leading-relaxed text-ink/60">
          愛蔵版・完全版・ワイド版・新装版など、<b>通常版より冊数が減っている版</b>だけを集めました。
          長い作品ほどまとめ買いしやすく、棚にも置きやすい版です。
        </p>
      </div>
      <AizoubanListClient />
    </div>
  );
}
