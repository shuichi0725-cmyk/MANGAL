# series 分裂 構造解析 — シャングリラフロンティアを起点に

> 作成: 2026-05-30 (夜間自走解析)
> 種2 sqlite 不変 / 種3 不変 / 本番 yml 未再生成。 **解析 + 提案のみ**。 実装は Go サイン待ち。
> 関連 memory: [[madb-native-series-structure]] [[shu2-qid-is-author]]

## 0. TL;DR

- シャングリラフロンティア(以下 SLF)は **同一作品が 4 つの series_id に分裂**している。
- 原因は build (`_build-series-v2.py`) の **クラスタキー = `(単一著者, base_title, subtitle)` の完全一致**で、 これが 4 つの独立した「揺れ」で割れる。
- これは SLF 固有ではなく **全 DB で約 10,018 作品 / 20,962 series 行が分裂**しているシステム的問題。 上位はゴルゴ13・美味しんぼ・うる星やつら・タッチ等の超有名作。
- 全ての揺れを貫いて安定している唯一の信号 = **ndla 名寄せ済み dcterms:creator 著者集合**(既に `series_authors` に計算済)。 これが build のクラスタキーにも promote の統合キーにも使われていないのが根本欠陥。
- **著者集合 + 正規化 title** で統合シミュレーションすると、 **9,969 group(20,841 → 9,969、 series 行 10,872 削減)が安全に統合**でき、 番外編/外伝等で別ページ維持が正当な **保留はわずか 56 group**。 SLF・美味しんぼ・代紋は正しく 1 作品に集約、 釣りバカ番外編等は正しく分離。

---

## 1. 現象: SLF の 4 分裂

| sid | series_key | 巻 | 分裂要因 |
|---|---|---|---|
| 141297 | `name:不二涼介\|name:シャングリラフロンティア` | 19,21〜26 | 著者キー=作画者 + subtitle **なし** |
| 141298 | `name:硬梨菜\|name:シャングリラフロンティア\|sub:クソゲーハンター、神ゲーに挑まんとす` | 2〜18 | 著者キー=原作者 + subtitle **あり** |
| 141299 | `name:硬梨菜\|…\|sub:…挑まんとす.` | 16 | subtitle 末尾 **`.`** 揺れ |
| 77559 | `name:硬梨菜\|name:シャングリラ・フロンティア\|sub:…` | 1 | title **中点「・」** + 役割違い著者 |

(vol 20 は MADB 取込もれ → 種4 `volumes-supplement.yml` で補完済)

**3 つの独立した分裂軸**:
1. **著者キーの不安定**: schema:creator テキストの並び順先頭を採用するため、 巻によって不二涼介(作画)が先頭か硬梨菜(原作)が先頭かで `name:` 部分が変わる。
2. **subtitle の有無**: 後期巻(19〜)は MADB が subtitle を落とした → 別クラスタ。
3. **title / subtitle の表記揺れ**: 中点「シャングリラ・フロンティア」、 subtitle 末尾ピリオド。

---

## 2. 根本原因: build のクラスタキー設計

`_build-series-v2.py` 行316:
```python
cluster_key_part = qid if qid else f"name:{matched_name}"
clusters[(cluster_key_part, base, subtitle)].append(record)
```

- `matched_name` = `extract_creator_names()` が返す名前の **先頭1名**(schema:creator のテキスト順依存)。
- `base` / `subtitle` = `parse_label()` が ` : ` で割った **生テキスト**(正規化なし)。
- → 著者・title・subtitle のどれか1つでも揺れると別クラスタ = 別 series 行。

重要: c27c049 の C-ID 著者改修で **`authors` フィールド(series_authors)は ndla 名寄せ済みで安定**しているが、 行298 のコメント通り **クラスタ判定には意図的に使っていない**(series_key を Wikidata-only に凍結 = 種3 を壊さないため)。 つまり「正しい著者集合」を計算済みなのにクラスタリングに使っていない。

### MADB ネイティブ信号の検証(SLF 25巻)

| 信号 | SLF での実態 | 結論 |
|---|---|---|
| `schema:isPartOf`(巻→C-series 容器) | vol 1〜5 のみ C447634、 6〜26 は容器なし | **5/25 しかカバーせず単独では不可** |
| C-series 容器 `schema:numberOfItems` | C447634 = 5 | 容器が途中で更新停止 = 不完全 |
| **`dcterms:creator` C-ID** | 全25巻が C427784(硬梨菜)を共有。 不二涼介は C53303(1〜11巻)→ C427785(12〜26巻)と C-ID が変わるが **両方 ndla=001231747** | **ndla 名寄せ後の著者集合 `{硬梨菜, 不二涼介}` は全25巻で完全一致** ★本命 |

→ **頑健なクラスタ軸 = ndla 名寄せ済み dcterms:creator 著者集合**。 isPartOf 容器は補助ヒント止まり。

---

## 3. システム規模: 全 DB の分裂

`series_authors`(ndla 名寄せ済)の著者集合 + 正規化 title で「作品シグネチャ」を作り、 2+ series に分裂しているものを集計:

- **分裂作品: 約 10,018 / 含まれる series 行: 20,962**

巻数合計 上位(影響大):

| 作品 | 分裂数 | 総巻数 | 主因 |
|---|---|---|---|
| ゴルゴ13 | 2 | 792 | subtitle「フォアメン」分離 |
| 美味しんぼ | 3 | 308 | **qid(花咲アキラ)vs name(雁屋哲)** 著者キー不安定 |
| うる星やつら | 3 | 190 | アニメコミック(スタジオぴえろ)混入(後段 drop 対象) |
| タッチ | 4 | 125 | subtitle「box」/原画集 + **`タッチ.` 末尾ピリオド** |
| 代紋TAKE2 | 4 | 143 | qid-vs-name + **「代紋 TAKE 2」スペース揺れ** |
| はじめの一歩 | 2 | 149 | **森川 vs 森川ジョージ** 名前切れ |
| 名探偵コナン | 2 | 176 | 1巻だけ **吉村勲(編集者?)を著者誤採用** |

### 分裂原因の分類

| 原因 | 例 | 性質 |
|---|---|---|
| A. qid-vs-name 著者キー不安定 | 美味しんぼ, 代紋 | **真バグ**(著者集合は同一) |
| B. 原作/作画/スタジオ/編集者 の採用ブレ | コナン(吉村勲), うる星(ぴえろ) | **真バグ** or 後段 drop |
| C. 著者名の切れ/表記揺れ | はじめの一歩(森川) | **真バグ** |
| D. title の punct/スペース/中点揺れ | 代紋 TAKE 2, SLF 中点 | **真バグ** |
| E. subtitle の有無/末尾ピリオド | SLF, タッチ. | **真バグ** |
| F. 別ページが正当(部/編/外伝/番外) | 釣りバカ番外編, ジョジョ各部 | **保留**(分裂でなく正しい分離) |
| G. 後段 drop 対象(アニメコミック/画集/抜粋本) | うる星ぴえろ, タッチ原画集 | 無害(promote で除外) |

A〜E が「根本的に直すべき分裂」、 F が「触ってはいけない正当な分離」、 G は既存フィルタで消える。

---

## 4. なぜ現 promote 層の救済では足りないか

promote (`_promote-bulk-v2.py`) には既に救済機構がある:
- `build_parent_map`: 同 qid + title prefix → 親子(スピンオフ)検出。
- `find_related_series_ids`: **同 qid** で title 一致 / **完全一致 title** で qid=NULL orphan を統合 + publisher check。
- `_strip_trailing_punct` / `_normalize_kana` / `_title_punct_suffix`: 表記揺れ吸収ヘルパー群。

**構造欠陥**: これらの統合キーは **qid(Wikidata 単一著者)または完全一致 title** に依存している。 だが分裂の原因はまさに **qid/name の不安定**と **title 揺れ**。

- 美味しんぼ: sid=25780 は qid=Q11615162、 sid=113235 は qid=**NULL**(name:雁屋哲)。 → 同 qid 経路では結べない。
- 全分裂を貫く安定信号 = **著者集合** は promote の統合キーに使われていない。

`series-merge.yml` の `merge_sids:` で個別パッチは可能(SLF の 23/26巻 deluxe で既に使用)だが、 **10,000 件規模を手動列挙するのは非現実的**。

---

## 5. 提案: ndla 著者集合ベースの正規化(canonicalization)層

### 設計方針

**build の series_key は不変のまま**(種3 join 維持・純粋追加・可逆 = CLAUDE.md 保護策と同レベル)、 promote/audit の統合段に **「作品 canonical 化」パス**を追加する。

```
canonical work key = (frozenset(ndla 名寄せ済 著者 C-ID 集合), normalize(base_title))
```

- `normalize(base_title)`: 中点「・」/ 半角全角スペース / 末尾 punct / `:` 等を strip(既存 `normalize_for_lookup` + `_strip_trailing_punct` を流用)。
- subtitle gating: subtitle が **semantic marker(第/部/編/外伝/前後編/番外/章/完結)を含む group は auto 統合しない**(別ページ維持 = 分類 F の保護)。
- それ以外(無印 + 装丁差 + punct 差)の group は同一作品として統合。 main = 最多巻数 sid。

### 実装オプション(2案)

- **案A(推奨)= series-merge.yml への自動 merge_sids 注入**
  - 既存機構(promote/audit が読む)をそのまま使う。 sim 結果を `merge_sids:` entry として **追記生成**。
  - 利点: series_key 不変・種2 不変・種3 不変・**完全可逆**(yml を消すだけ)・既存 consumer 不変。
  - 56 件の保留 group のみ人手レビュー → 別ページ維持 or 個別 merge を判断。
- **案B = `find_related_series_ids` の統合キーに著者集合を追加**
  - qid/完全一致 title に加え「著者集合一致 + 正規化 title 一致」経路を追加。
  - 利点: yml 肥大化しない、 新規取込にも自動追従。 欠点: promote ロジック変更 = テスト必要、 over-merge を gating で防ぐ実装が必要。

→ **まず案A で 9,969 group を一括投入 + 56 件レビュー、 将来 案B で恒久化**が安全。

### シミュレーション実測(`scripts/_sim-author-set-merge.py`)

```
auto_merge groups : 9,969   (series 20,841 → 9,969)
sid reduction     : 10,872
held (manual)     : 56
```

- SLF(77559,141297,141298,141299)・美味しんぼ(25780,113235,113236)・代紋(4 sid)→ 全て正しく 1 作品に集約。
- 釣りバカ日誌番外編・今日から俺は劇場版セレクション・カラテ地獄変正編/新章 → 正しく **保留**(別ページ維持)。
- 提案全件: `.cache/proposed-author-set-merges.json` / `.csv`(レビュー用)。

### 残リスク(要レビュー)

1. **same-author-set + same-normalized-title だが別作品**: 著者集合完全一致 + title 完全一致を要求するため確率は低いが、 同一作者の同名読切が稀に衝突しうる。 → **レビュー対象は保留 56 group のみで十分**。
2. **distinct_qids≥2 は誤統合フラグではない(確認済)**: auto 9,969 のうち 307 group が 2+ の Wikidata QID を持つが、 これは **2 著者作品(原作+作画)で両者とも Wikidata 既知**という正常パターン。 あしたのジョー(梶原一騎+ちばてつや)・子連れ狼(小池一夫+小島剛夕)・終わりのセラフ(鏡貴也+降矢大輔+山本ヤマト、 著者集合は両 sid 完全一致で series.qid だけ別)等を実体確認 = 全て同一作品の正しい統合。 → **307 件はレビュー不要**。
3. **semantic marker の取りこぼし**: 「SEASON2」等 英字 marker。 marker list は要拡充。
4. **著者ゼロ series**(6,669 件)は本解析の対象外 = 著者集合が空のため別途。

---

### 保留 56 group の事前分類(`.cache/held-groups-classified.txt`)

保留 56 group を確認した結果、 **「全部別ページ」ではなく group 内で部分統合が必要**と判明:
- 釣りバカ日誌: sub なし 2 sid(117262+11028)は**統合**、 「番外編」(117263)だけ**別ページ**。
- 将太の寿司: 「全国大会編」2 sid は相互統合、 本編(48621)とは別ページ判断。
- ドカベン: 本編 + 「名勝負編」= arc 別ページ。 鬼平犯科帳: 本編 + ワイド版(=edition 統合)+ ベストセレクション/総集編(=後段 drop)。

→ 現 sim の gating(「semantic sub が 1 つでもあれば group 全体を保留」)は保守的すぎる。 **実装時は held group 内でも sub なし/装丁差は統合し、 arc/番外/部 だけ分離**する 2 段 gating が必要。 この 56 group の arc 境界判断は CLAUDE.md「各漫画=個別ページ、 部/スピンオフは別ページ」哲学に直結するため **ユーザ裁定が望ましい**(自動化しない)。

## 6. 次アクション(Go サイン待ち)

1. `.cache/proposed-author-set-merges.csv` をユーザがレビュー(特に held 56 + distinct_qids 2+)。
2. OK なら 案A: sim → `series-merge.yml` 追記生成スクリプトを作成(既存 `_gen-series-merge.py` と同形式、 merge_sids entry を append)。
3. 本番 yml 再生成 → SLF が 1 ページ(全26巻)に集約されることを確認。
4. 将来: 案B で build/promote に恒久組込 + marker list 拡充。

**現時点で本番 db / 種3 / series-merge.yml は一切変更していない。**
