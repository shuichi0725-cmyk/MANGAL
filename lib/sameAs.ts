// 作品頁 JSON-LD の sameAs(= 「この作品はあの項目と同一」の機械向け宣言。2026-10-22 ユーザGO)。
// 画面下部の「外部リンク」と同じIDのうち、**作品**の2つだけを使う。
// ★罠: 頁データの wikidata_qid は**著者**のQID(series.qid)、作品は work_wikidata_qid。取り違えると
//   「作品=著者」と宣言してしまうので、作品側には work_wikidata_qid と anilist_id だけを使う。
// ★著者(Person)には sameAs を付けない: 著者1人の頁でも wikidata_qid が別人(原作者・別作家)の頁が
//   抜き取り 3/40(7.5%)あった(2026-10-22 実測: ライブマシーン 松森正→狩撫麻礼 等)= 誤った同一宣言になる。

type SameAsInput = {
  anilist_id?: number;
  work_wikidata_qid?: string;
};

export function workSameAs(m: SameAsInput): string[] {
  const out: string[] = [];
  if (m.work_wikidata_qid) out.push(`https://www.wikidata.org/wiki/${m.work_wikidata_qid}`);
  if (m.anilist_id) out.push(`https://anilist.co/manga/${m.anilist_id}`);
  return out;
}
