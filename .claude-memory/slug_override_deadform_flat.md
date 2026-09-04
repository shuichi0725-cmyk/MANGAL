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
1. **`data/slug-aliases.yml` に 旧slug→新slug を足す**(★ここが正本。連鎖はそのまま残してよい=来歴)
2. `public/_redirects` と `.cache/redirects.json` は **`python scripts/_gen-redirects.py` で再生成**する
   (手で書き足さない。生成器が終端まで畳んで1ホップにするので、Cloudflareがチェーンを辿らない問題は起きない)
3. 掲載外(non-manga-drop)の頁は promote が出力しないので `--only` に入れない(検証ゲートが止まる)

**続き(2026-09-05 ユーザGO)**: 検出器 `scripts/_audit-slug-kana-loanword.py` の DEVICE_DIFF から
**CLEAR層116頁**を `scripts/_apply-slug-kana-loanword.py` で適用済み(rosutowaarudo→lost-world /
danjonmeshi→dungeon-meshi / kodoku-no-gurume→kodoku-no-gourmet 等)。CLEAR の3条件=
①英語をカナのローマ字へ逆置換すると現slugに戻る ②★カタカナ連が辞書語で**丸ごと**覆える
(ディアナ→ディア+ナ の「長い外来語の頭だけ食う」型が最大の偽陽性源) ③日本語側のハイフン不変。
★機械ゲートを通っても意味で誤る型があるので EXCLUDE を持つ(超人ロック=親頁 choujin-locke /
鍵師ロック=lock であって rock でない / アウト・ロー=outlaw)。
**残 REVIEW 702件** は suggest列が答えではないので per-case 裁定が要る。

★**改名で踏んだ事故2つ(番人を入れた)**:
1. **重複キー**: 同じキーを2度書くと YAML は後勝ちで、先の指定が黙って無効になる
   (oirangaaru で oiran-girl が oiran-gaaru に負けた)。`_check-seeds.py` が**行を数えて**FAIL する。
   yaml.safe_load では潰れて見えないので、必ず行で数えること。
2. ★**逆向きalias**: 改名で新slugが公開されると、以前から在った `新slug: 旧slug` の alias が
   **公開中の頁を404へ301する**(slow-loop→surooruupu で実踏)。`_gen-redirects.py` が
   ①aliasのキーが公開slug ②宛先が未公開 の2つを毎回数えて警告する。改名したら必ず生成物を見る。

★**多段リダイレクトは問題ではない**(2026-09-05 検算で自分の誤報を訂正): `_gen-redirects.py` が出力側で連鎖を平坦化する設計で、`slug-aliases.yml` は改名の**来歴**として連鎖のまま残すのが正しい。生成物(public/_redirects・KV redirects.json)は 宛先未公開0・多段0 で健全だった。ymlを畳もうとすると来歴を壊すのでやらないこと。

関連: [[slug_cluster_fix_and_changelog]] / [[drop_page_redirect_chain]] / [[feedback_one_bug_means_a_class]]
