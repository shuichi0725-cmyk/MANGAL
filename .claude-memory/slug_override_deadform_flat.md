---
name: slug_override_deadform_flat
description: slug-overrides.yml は overrides:配下の入れ子dictしか効かない。平坦形old:newは書いても無効(2026-09-05に142件移行・FAILで封鎖済)
metadata: 
  node_type: memory
  type: project
  originSessionId: 74b7cb9b-8792-4d9b-a5f5-6e0efb70e9e8
  modified: 2026-09-04T16:47:49.016Z
---

`data/seeds/slug-overrides.yml` は **promote の `_slug_override` が
`doc["overrides"]` 配下の「入れ子dict かつ `slug` キー付き」しか読まない**。

```yaml
overrides:
  old-src-stem:
    at: '2026-09-05'
    reason: なぜ直すか
    slug: new-public-slug     # ← これが無いと読まれない
```

トップレベルの平坦形 `old: new` と、overrides配下でも値がstrのものは **書いても永久に効かない**。
書いた人は直したつもりでいるので silent = [[katakana_dict_dead_entry_trap]] と同じ型。

**発覚(2026-09-05)**: ユーザ指摘「猫と紳士のティールームがヘボン」
(`neko-to-shinshi-no-teiiruumu`)。1件のバグを型として掃いたら、平坦形143件のうち
**116件が旧slugのまま公開中**だった(`999-dokutaa` / `dekinbooi` / `aho-jiru-reinboo` …)。

**是正済み**: 125件を効く形へ移行し公開URL121件を差し替え。保留17件は消さず
`not_applied:` セクションへ退避(SRC不在15 / 入れ替えの片側2)。
`_check-seeds.py` の死に形検査を **FAIL** に格上げ済み = 以後 平坦形を書くと反映もintakeも止まる。

**キーは SRC の内部slug**(= `data/manga/<key>.yml` のファイル名と一致)。
`data/manga.v2` は出力側なので混同しない([[edition_canonical_key_is_src_slug]] と同じ注意)。

**改名に必ず付いてくる3点**:
1. `data/slug-aliases.yml` と `public/_redirects` に 旧slug→新slug
2. ★**既に旧slugを指していたリダイレクトは新slugへ張り替える**(Cloudflareはチェーンを辿らない=多段は404)
3. 掲載外(non-manga-drop)の頁は promote が出力しないので `--only` に入れない(検証ゲートが止まる)

**残**: 検出器 `scripts/_audit-slug-kana-loanword.py` の DEVICE_DIFF 834件
(台帳に無く、装置なら英語綴りを出す頁)。★suggest列は答えではない = 装置が語境界を
取り違え `choujin-locke`→`choujin-rock` のように現状の方が正しい行が残るので per-case 裁定が要る。
別件の負債として **多段/切れリダイレクト649件**(短母音表記ゆれ由来)も在る=未着手。

関連: [[slug_cluster_fix_and_changelog]] / [[drop_page_redirect_chain]] / [[feedback_one_bug_means_a_class]]
