---
name: duplicate-slug-two-files-blindspot
description: "同じslugを名乗るmanga.v2ファイルが2つ在ると索引に同一作品が2行出るが、検出器#19は入力をby_slug dictに畳むため見えない。掃引はgrep -H \"^slug:\" の1パス(10秒)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4cce8a9c-a5ff-4f2c-a19f-a21245d006b2
  modified: 2026-09-14T14:03:16.368Z
---

`data/manga.v2` は **ファイル名(SRC stem) ≠ 頁の `slug:` 欄(公開slug)** が正常形(slug-override頁)。
このため「**別名のファイル2つが同じ公開slugを名乗る**」状態が作れてしまい、全索引ビルドで**同一作品が2行**出る。

★2026-09-14 実踏: `白と黒`(下崎)。
- 生 = `shiro-to-kuro-shimozaki2026.yml`(源 `source-pages/` 有り・`promote --only` で total:1)。status=completed/genres/catch/synopsis 完備
- 残骸 = `shiro-to-kuro-shimozaki.yml`(2026-09-07・**源なし** total:0・genres空)
→ 残骸を削除して索引 69,353 → 69,352。旧URLの301は別途 slug-aliases/_redirects に在るので無傷。

**Why:** 検出器#19 `_audit-year-suffix-dup.py` は入力が `by_slug = {str(r[SI]): r for r in idx["d"]}`
= **同一slugの行が黙って後勝ちで畳まれる**ので、この形を構造的に見られない(#19が見るのは
`X-YYYY` と `X` という**別slug名**同士の対)。同じ理由で「索引の重複slug数」を#19では測れない。
残骸が生まれる経路 = 頁の公開slugを変えた(年サフィックス外し等)時、**旧名のファイルが残る**。
`data/manga.v2` はgitignore = 履歴が無いので気づけない。フルpromoteは先頭で全unlinkするので
月次を回せば自然消滅するが、それまでの差分反映/索引ビルドでは二重のまま出る。

**How to apply:**
- ★掃引は**ファイル実体**を見る(索引を見るな)。10秒で済む:
  `grep -H "^slug:" data/manga.v2/*.yml` → ファイル名と `slug:` 欄の対を作り、slug側でCounter
- どちらが生きているかの判定 = `python scripts/_promote-bulk-v2.py --only <stem>` の **total:** 。
  `total: 1` = 源あり(残す) / `total: 0` = 源なし(残骸)。中身の厚み(genres/catch有無)でも裏が取れる
- 消す前に `.cache/` へ退避。索引は `_build-list-index.py data/manga.v2 data --update <生stem> --remove <slug>`
- **未登録**: この掃引は月次サニティの検出器になっていない(#19は上記の理由で代用不可)。
  登録するなら `scripts/_check-sanity-registry.py` の3点突合(CLAUDE.md索引 / docs本文 / DETECTORS)に乗せる = ユーザGO待ち
- 関連: [[pubslug_src_stem_generator_trap]] [[slug_rename_kills_slugkeyed_seed]] [[orphan_source_pages_restored]] [[year_suffix_slug_survey]] [[feedback_one_bug_means_a_class]]
