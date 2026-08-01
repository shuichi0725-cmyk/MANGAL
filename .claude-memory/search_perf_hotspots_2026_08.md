---
name: search_perf_hotspots_2026_08
description: 本番67kが遅い実測内訳=カナ数詞fold86%/alt到着で全再構築/巨大単一タスク。2026-08-01に是正済
metadata: 
  node_type: memory
  type: project
  originSessionId: 9e4afa8a-543a-4b77-966f-1cb6d5cb07d4
  modified: 2026-08-01T00:37:22.769Z
---

★本番(68,749件)が preview(1,229件)より桁違いに重かった**実測の内訳**と是正(2026-08-01)。同種の症状が出たらここを起点に。

- ★**カナ数詞 fold が `normalizeForSearch` の86%**(4,729ms)。17語×(カタカナ+ひらがな)を split/join で最大34回全文走査し、
  さらに**ひらがな形をループ内で毎回 replace して作り直していた**。交替正規表現1本に → **31ms**。全体 5,510→721ms。
  等価性は `lib/romaji.foldNumerals.test.ts` が**旧実装をオラクル**に実索引の全文字列36万本+語の全組み合わせで突合(不一致0)。
- ★**alt(別名)到着のたび haystack を全再構築**(5,128ms)= 「**検索して件数が出た直後にまた固まる**」の正体。
  alt は照合材料を**増やす方向にしか働かない**ので、未畳み込みの hay には題名欄への**文字列追記だけ**で等価 → 68ms。
- ★**idle に載せても「1本の巨大タスク」なら主スレッドは返らない**(haystack 4.5秒)。器を先に作り 500行ずつ空き時間で埋め、
  検索が先に来たら残りを同期で埋める(結果は常に完全)。総量も 12,225→2,714ms。
- ★一覧の人気順は**48.5%が popularity 未設定**でほぼ全比較が最終タイブレークの文字列比較まで落ちる。
  `lib/collator.ts` の共有 Collator へ(`localeCompare` 都度呼び禁止)。292→213ms。
- 著者50音リスト(119ms)は **FilterPanel が open の時だけマウントされるのに索引到着と同時に走っていた** → 抽斗を開くまで作らない。
- ★**HomeClient のデスクトップ用 FilterPanel は `hidden md:block`= モバイルでも React はマウントされる**(CSSで隠れているだけ)。
  つまりモバイル利用者も 67k件×7パスの動的件数と著者リストを払っている。**未着手**(マウント条件を変えると水和のちらつき懸念)。
- 残る重さ = wanakana の `kanaToRomaji`(36万本で約3.7秒)。ローマ字層だけ遅延構築する案は**未着手**。

関連 [[search_snapshot_gate]] [[lightweight_index_architecture]]
