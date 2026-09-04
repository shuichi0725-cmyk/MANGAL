---
name: pubslug-src-stem-generator-trap
description: "生成器がmanga.v2を公開slugで直引きすると改名頁(slug-overrides 1,927件)が全欠けする型。逆引きpub2stem必須"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0ba33c01-29d0-4e64-81d1-992e4247640b
  modified: 2026-08-31T07:03:06.753Z
---

**型**: 索引/カレンダー等の生成物は**公開slug**を持つが、`data/manga.v2/*.yml` のファイル名は**SRC stem**。
slug-overrides.yml で改名された頁(overrides含む~1,927件)は両者がズレるため、
公開slugで `data/manga.v2/{slug}.yml` を直引きするコードは**無警告で頁を見失う**。

**実踏** (2026-08-31): `_gen-shinkan-data.py` がこれで新刊一覧の書影/ISBN/著者/出版社を全欠けさせた
(2026-06で93/100冊。slug-fix-834改名頁が集中)。症状は「書影抜け」だが根因はslug結線。

**Why**: [[edition_overrides_key_is_public_slug]] / [[edition_canonical_key_is_src_slug]] と同族の
キー空間取り違え。seed層だけでなく**生成器(read側)にも同じ罠がある**と分かった。

**実踏2 = ★書き込み(削除)側にも同じ罠** (2026-09-04): `_deploy-differential.py` は
**PUT は公開slug・DELETE/purge/IndexNow通知は SRC stem** で、キー空間が経路ごとに混ざっていた。
帰結= stem≠slug の頁を消すと **R2に本物が残り(孤児頁)、存在しないURLを purge/通知**する。
実測: 次の差分反映で消える51頁のうち **4頁**が該当(devilman-lady-2000 / ryojou-mystery-special-2020 /
shikakenin-fujieda-baian-saitou2002 / tales-of-the-abyss-rei2006)。
★**消えた頁は yml が無いので slug を引けない**のが厄介所。 解決の実装見本 =
`_deploy-differential.resolve_pub_slug()` + `load_slug_ledger()`:
`.cache/prod-page-slugs.json`(週次 `_init-pages-manifest.py` が生成)→ `slug-overrides.yml`(頁を消しても残る)
→ **本番 r2-manifest の実在で検算** → stem。 51/51 が本番実在キーに解決することを確認済み。

**How to apply**:
- manga.v2 をslugで引く新規スクリプトは必ず `slug-overrides.yml` の逆引き(公開slug→stem)をフォールバックに持つ。実装見本= `_gen-shinkan-data.py` の `load_pub2stem()`(旧142件の平置きsection+`overrides:` sectionの両方を読む)。
- 「特定期間だけメタが全空」の症状を見たら、その期間の改名バッチ(slug-fix等)を疑う。
- ★**新しいデプロイ経路を書いたら「PUT / DELETE / purge / 通知」で使うキー空間が揃っているか必ず見る**。
  1経路だけ stem のままでも本番からは消えず、症状は「消したのに残る」= [[r2_orphan_pages_prune_missing]] に化ける。
