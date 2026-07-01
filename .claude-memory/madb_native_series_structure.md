---
name: madb-native-series-structure
description: "MADB は isPartOf(巻→シリーズC-ID) と dcterms:creator(作者C-ID) で容器構造を提供済み。種2 build はこれを無視して名前パースで再構築し問題#1/#2 を生む"
metadata: 
  node_type: memory
  type: project
  originSessionId: a03f249f-ccd2-4c14-88f9-305069eb1cc5
---

MADB 生データは「マンガ単行本シリーズ」容器構造をネイティブに持つが、現 build (`scripts/_build-series-v2.py`) はそれを無視して名前テキストから再構築している。これが既知の2問題の共通根因。

**MADB のデータモデル (metadata101/104 で確認):**
- `class:MangaBookSeries` (C-prefix, 例 C290221「ゼロ」) = 作品=容器。metadata104 に格納。
- `class:MangaBook` (M-prefix, 例 M263482「ゼロ v.1」) = 巻。metadata101 に格納。
- 巻→容器リンク = `schema:isPartOf` (= シリーズ C-ID)。全books の **81.9%** が保有。
- 作者 = `dcterms:creator` (= 安定した C-ID、容器record と巻record で共有)。全books の **93.9%** 保有。
- `ma:originalWorkCreator` = 原作者だけを分離 (例 `[原作]愛英史`)。
- `schema:numberOfItems` = シリーズ総巻数 (ゼロ=78)。
- C-series 粒度が MANGAL の「1作品1ページ」方針 (CLAUDE.md) とほぼ一致。ゼロ本編/special edition/完結編/J 等を MADB が別容器で正しく分離済み。

**現 build が捨てているもの / 起きる問題:**
- クラスタキーを `(creator_name テキスト, base_title, subtitle)` のヒューリスティックで作る → isPartOf を未使用。
- 作者を `schema:creator` テキストから `[著]/[作]` 優先で1人だけ採用 → `[原作]` を拾い `[漫画]/[作画]` を落とす ([[shu2_qid_is_author]] と関連、問題#2 = 約4,328シリーズで作画者脱落)。
- デラックス→shinsoban 誤分類は `_populate-v2.py` の独自ルール (問題#1 = 2,609シリーズ、shinsoban の99.6%)。

**Why:** ゼロ(C290221, 里見桂/愛英史)で発覚。種2 sid=79110 が作者空 + 77巻が新装版誤分類。ユーザが MADB web の作者C-ID(C70602/C57310/C53202)に着目して指摘。

**How to apply (2026-05-29 修正):** クラスタ軸は **isPartOf容器ではなく「作者(ndla名寄せ)+base_title」**。検証で isPartOf 容器は不完全と判明 (シャングリラフロンティア本編26冊中、容器C447634 は5冊しかカバーせず21冊は容器なし)。容器は補助ヒント扱い。改修の肝:
- 作者解決を `schema:creator` テキスト1人採用 → `dcterms:creator` の **C-ID 全部** を 504 で名前化し **両著者(原作+作画)保持**。
- **C-ID は1人に複数ある** (高橋留美子=C427550/C49857/C523272、不二涼介=C427785/C53303)。`ma:ndla` (NDL authority 8桁) で名寄せ統合してから作者キーにする。
- これは現 build と同じ「作者+title」軸だが、壊れやすい名前パースを C-ID→504→ndla の安定チェーンに置換するのが本質。

**mangaka.csv 拡充 実施済 (2026-05-30)**: MADB 504 由来作者を `data/seed/mangaka-madb.csv`(42,115名、合成キー `ndl:<8桁>`/`madb:<C-ID>`)に分離生成(`scripts/_build-mangaka-madb.py`)。`_db-init-v2.py` が mangaka.csv と両方 seed、`_build-series-v2.py` は resolve_authors 用 name_to_qid だけ merged(clustering は Wikidata-only 凍結 = series_key 不変・種3無傷)。結果: 著者ゼロ series 99,862→6,669、series_authors 66,579→229,620、原作者(大場つぐみ/愛英史)も紐付く。成年は `_apply-adult-filter-v2.py` の signal3 を「全著者 × MADB成年比率の重み(adult_mangaka_known 2,035名と照合)」に強化、クロスオーバー(楳図かずお=比率0)保護。mangaka.csv 本体(Wikidata 6,751、非成年キュレーション)は不変。**残: NDL→Wikidata(P349)で `ndl:` を実Qに昇格 + birth_year enrich**。

**作者マスター = metadata504.json (取得済 2026-05-29)**: class:Agent 74,982件、C-ID→名前。MADB dataset release (github.com/mediaarts-db/dataset, tag 1.2.16) の metadata504_json.zip。`.cache/madb/metadata504.json` に展開済。
- `schema:name`/`rdfs:label` = 名前 (C-ID 解決の本命)
- `ma:additionalGenre` = 個人(70,654)/団体(4,328) = 人/組織区別。ただし不完全(ホーム社が個人と誤タグ)。
- `ma:ndla`(46,078) NDL authority / `ma:wikidata`(~1,972) Wikidata QID直結 / `ma:viaf` 等の外部ID。birthDate/hasOccupation/twitter 等も有。
- 解決チェーン: dcterms:creator C-ID → 504 schema:name → mangaka.csv の name/alt_names → qid。wikidata QID 直結は mangaka.csv qid と20件しか交差せず低カバレッジ、name 経由が本命。
- ゼロ実証: C53202→里見桂→mangaka.csv Q11644656(作画◎)、C70602→愛英史(原作=漫画家でなく mangaka.csv 外で正しい)、C57310→ホーム社(団体=編)。
- 注: metadata505 は class:Event(25件)で無関係。作者マスターは504。
