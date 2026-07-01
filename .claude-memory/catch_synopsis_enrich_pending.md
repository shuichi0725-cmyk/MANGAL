---
name: catch_synopsis_enrich_pending
description: 【harvest後】2巻以上のキャッチ/説明文欠落リスト+Web取得の方法(試金石成功済)。巻数多い順Top100から
metadata: 
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

本番でキャッチコピー/詳細説明(synopsis)が欠けてる漫画を、Web検索で補強/生成する作業(2026-06-27方針確定。★楽天harvest完了後に実行)。

## 調査リスト(commit済)
- `docs/missing-catch-synopsis.tsv` = 2巻以上で欠落 27,954件(両方欠20,620/説明欠6,318/キャッチ欠1,016)。
- `docs/missing-catch-synopsis-2000plus.tsv` = **2000年以降+2巻以上**で欠落 **19,750件**(両方欠13,564/説明欠5,433/キャッチ欠753)。列=slug/title/year/volumes/missing。
- ★検出法: 巻数/catchは索引+catch-index、synopsisのみ `rg -P "^synopsis: (?!'')\S"` で充填済判定(yml全読み不要)。synopsis充填済=20,115頁。

## Web取得の方法(試金石2件で成功実証)
- **WebFetch(ja.Wikipedia優先→無ければ公式/検索)** で **あらすじ(80-120字要約)/分野(カテゴリー)/要素(テーマ・舞台)** を抽出=信頼性高く取れる(弱虫ペダル・絶対可憐チルドレンで確認)。
- ★**キャッチコピーはWikipediaに無い**(公式宣伝文)→ **抽出したあらすじからAI生成**(数十字の惹句)。「無いものは作る」。
- ★ジャンル/要素は**既存32キーclosed vocabularyにマッピング**([[ai_genre_closed_vocabulary]]・新語禁止)。synopsis和訳seedは[[synopsis_ja_seed]]の形で永続化。
- 規模: 巻数多い順Top100から(`.cache/test-top100.tsv`は再生成可=上記TSVを巻数降順Top100)。並列workflowで効率化可(ユーザOK要)。出力TSVで本番反映前レビュー。

## 関連
[[genre_from_rakuten_story_plan]](楽天あらすじ→ジャンル生成の前例)/[[tagless_coverage_next]]/[[monthly_intake_reality]]。
