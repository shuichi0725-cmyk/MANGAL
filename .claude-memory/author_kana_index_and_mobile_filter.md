---
name: author-kana-index-and-mobile-filter
description: 【残タスク】スマホUX2件=①著者あかさたな50音索引(読みデータ土台AniList41%取得済・NDL補完要)②フィルターを透過オーバーレイ化
metadata: 
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

【ユーザ依頼 2026-06-05・スマホ版MANGALのUX改善2件。 PC版は問題なし=スマホのみ変更】

## ① 著者の あかさたな 50音索引(本番で著者大量増→現multi-select著者listでは探せない)
- ★UI: 「あ か さ た な は ま や ら わ」行 → 押すと「あいうえお」展開 → 該当頭文字の著者だけ表示。
- ★**前提=著者の読み(かな)が要る**。 mangakaマスター(`data/seed/mangaka.csv`=Wikidata由来 / `mangaka-madb.csv`=MADB由来)とも**読み列なし**。 alt_namesは読み/あだ名/None混在で使えない(高橋留美子・鳥山明すらalt無)。
- ★**土台データ取得済(2026-06-05)**: `scripts/_extract-mangaka-yomi-anilist.py` で AniList dump(`anilist-manga-dump-v3.jsonl.gz`)の staff `name.full`(romaji)+`native`(漢字)→ jaconv で romaji→カタカナ読み。 結果 `data/seeds/mangaka-yomi-anilist.yml` = **18,460件(マスター日本語著者44,672の41%)**。 品質=純日本語native98%/壊れ読み0/著名作者全件正確。 latin名(CLAMP等)除外。
- ★**残**: カバレッジ59%(26,212名)未取得 → **NDL著者典拠**(著者標目=ヨミ有)で補完が本筋([[furigana_ndl_audit]]と同インフラ)。 + UI実装(行→かな→filter)。 著者filterは現在 名前string基準([[shu2_qid_is_author]])。

## ② スマホのフィルターを「透過オーバーレイ」化 → ★**実装・デプロイ済(2026-06-05)**
- `app/HomeClient.tsx`: スマホのフィルターを全画面オーバーレイ化。 ボタンで origin-bottom から scale 拡大(300ms ease-out)、 ×/「結果を見る」で畳む。 表示中 body スクロール固定。 PC版(md:)はサイドバー不変。
- ★最終形=**DQ風 透過枠ウインドウ**: frosted透過(`color-mix surface 28% + backdrop-blur-sm`)で背後の漫画がうっすら透ける + 余白(inset-3=多重ウインドウ感)+ 太白枠(border-4 border-white)+ 外側暗線(ring-1 black/30)+ 角丸(rounded-26px)+ 影(shadow-2xl)。
- ★調整余地(ユーザ「後で変えられる」): 枠の太さ(現4px→6-8px)/枠色(白→紺・金等)/余白量/透過度(現28%)。 ★淡色テーマ+書影なしで透け感は控えめ、 実書影が入れば背後がはっきり見える。

関連: [[filterpanel_show_counts]](FilterPanel別タスク=各チップに件数表示)。
