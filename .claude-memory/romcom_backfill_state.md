---
name: romcom_backfill_state
description: "【✅適用済】ラブコメ復権=romance∩comedy 7,184作を全裁定→romcom 2,939件をmanga.v2へ適用済(143→3,081)。残=本番R2公開(次の週次)"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-03T01:25:55.488Z
---

★**romcom枯れ問題**(2026-08-03 ユーザ発見「80年代のラブコメが6件」): romcom は全DB143作のみだった。
根因=注ぎ手(AniList/楽天/AI fill)が romance+comedy に割って romcom を出力しない構造。
候補=**romance∩comedy 7,184作**。ユーザ裁定=方式1(AI裁定バックフィル)→ コスト配慮で skill化。

## 現在地 (= 2026-08-03 適用完了)

- **裁定 完了**: 台帳7,184件 = yes 2,944(text-match 2,178 / ai-judge 766)/ no 2,762 / unknown 1,478。worklist残0。
- **適用 完了**: `genre-append.yml` へ2,939件を純粋追加 → targeted反映で **manga.v2 + 本番索引まで反映済**。
  本番索引の romcom = **143 → 3,081**。未適用は `konpaira-fesuta` 1件のみ(下記)。
- ★**残= 本番R2公開だけ**(manga.v2は更新済だが公開HTMLは古い)。**次の週次蒸留で自動的に出る**。
- ai-judge yes の無作為20件目視= 大半が材料に「恋愛コメディ/コメディ・ロマンス」明記の証拠ベース、
  知識判定の混入なし= 精度良好。

## ★実測ノウハウ (= 次回の横展開でそのまま効く)

- **反映は週次に任せられない**: 週次蒸留は `data/manga.v2` からビルドするだけで **promoteを走らせない**。
  seed(genre-append)を書いただけでは本番に出ない= **targeted反映が必須**。
- **大量slugのtargeted反映はチャンク必須**: `--only` はカンマ区切りargv= Windowsの32,767字上限に当たる
  (2,939 slugで79,419字)。**700 slug/chunk**(~19.6k字)で5回、`--commit-only` で溜めて最後に1回push。
  実測 **700頁/約65秒**= 2,939頁で計6.5分(フルpromote 110分に対し圧倒的に安い)。
- **seedキーは公開slug / --only はSRC stem** = 別物。manga.v2のファイル名=SRC stemで、
  slug-override頁は `data/manga.v2/<公開slug>.yml` が**存在しない**。解決= `grep -rn '^slug: <公開slug>$' data/manga.v2`
  (★`.gitignore`されているのでGrepツール[ripgrep]では引けない。bashのgrepを使う)。
- `konpaira-fesuta` = 種2に editions が無い(`no_editions`)= promoteが再生成できない**古い残骸頁**。
  romcom適用の対象外。ラブコメとは無関係の別件(要別途調査)。

## 派生して直した構造バグ (= [[genre_append_seed_mechanism]] に恒久修正済)

genre-append.yml が届かない2型を発見し `_promote-bulk-v2.py` を修正(commit a42b56d11):
1. **slug-override頁**(実測1,037件)= 適用点で引くキーが override **前**のSRC slugだった → 両方で引く。
2. **予約頁**(`data/seeds/preorder-pages`)= 種2を通らず本流の適用点に来ない → 予約ストリームにも同じunionを通す。

## 横展開(次の柱)

同型の「注ぎ手がいない枯れキー」: **4-koma 93**(数千あるはず・レーベル/楽天タグに強信号)/ gag 147 /
samurai 132 / mahou-shoujo 217 / war 194 / yokai 257。候補集合の作り方は各キーで別設計。
unknown 1,478件(材料無し)は**知名作の知識判定**をOpus+が別途やる余地あり。

関連 [[genre_append_seed_mechanism]] [[ai_genre_closed_vocabulary]] [[genre_quality_improvement]]
