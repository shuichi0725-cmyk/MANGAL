# 取込マニフェスト + 出荷ゲート 設計書

作成 2026-06-13 / ユーザ依頼「型別マニフェスト+出荷ゲートを慎重に設計」。
本書は設計のみ(未実装)。実装は段階導入(末尾 §7)。

---

## 0. なぜ要るか(動機 = 実証済みの痛み)

- **完成定義(Definition of Done)が無い**。今のパイプラインは「ページが生成された」=出荷、になっている。フィールドが空でも出る(ship-first 傾向、`feedback_complete_data_before_ship` に戒めはあるが**機械ゲートが無い**)。
- **何をチェックしたかの記録が無い**。監査部品は7つ存在するが(下記)、結果が**ページ単位で残らない**。次の蒸留で「何が足りなかったか」をまた総当たりで探す。
- **実証**: 2026-06-13 の成年漏れ(2,233ページ)。種2の `adult_score` 判定自体は正常だったが、slug 適用パイプラインに成年ゲートが**配線されていなかった**。「成年フィルタは走っているはず」という暗黙の前提を、出荷前に検証する仕組みが無かった。台帳があれば `adult_gate: (未実行)` として即座に発覚した。

### 既存の監査部品(=チェックの素材。台帳に束ねる対象)
| script | 何を flag するか |
|---|---|
| `_coverage-audit.py` | 真の公開数・被覆・品質 flag |
| `_audit-volume-numbering.py` | 巻番号異常3分類(AUTO_FIXED/MISSING_HALF/GAP_OTHER) |
| `_furigana-audit.py` | NDL公式読みとの不一致 |
| `_audit-foreign-editions.py` | 外国語版(ISBN国コード非9784) |
| `_audit-volume-gaps.py` | 内部欠け巻(取込もれ候補) |
| `_audit-trailing-gaps.py` | 末尾取込もれ(AniList総巻数 vs 種2max) |
| `_gen-publisher-keys.py` | 未キー出版社 |

→ これらは**ページ単位の判定を吐けるのに、結果が捨てられている**。マニフェストはこの出力を受け止める器。

---

## 1. 全体像(3部品)

```
  入口            台帳                    門番
┌─────────┐   ┌──────────────┐   ┌─────────────┐
│ 型分類器 │ → │ マニフェスト   │ → │ 出荷ゲート   │ → ship / hold / quarantine
│(差分判定)│   │(provenance+   │   │(型別必須を   │
└─────────┘   │ checks+holes) │   │ 満たすか判定) │
              └──────────────┘   └─────────────┘
                    ↑ git追跡seed(=次回蒸留が読む=総当たり回避)
```

- **型分類器**: 入ってくるレコード(or 影響を受ける本番ページ)を変更の型に分類。
- **マニフェスト**: 各ページ(orクラスタ)に「型・出所(provenance)・通したチェック・残る穴」を記録。git追跡 seed として永続化 → **次回蒸留が読む=台帳が記憶になる**。
- **出荷ゲート**: 型ごとの必須条件を満たすか機械判定。`ship:true` のページだけ本番に出る。

---

## 2. 型分類器(入口)= 変更の型を判定

各 incoming レコードを、本番現状との照合で型に振り分ける。判定キーは **ISBN** と **クラスタ所属**(NDL著者典拠ID + 正規化主題)。

| # | 型 | 判定条件 | 頻度 |
|---|---|---|---|
| 1 | `new_volume` | 新ISBN、既存クラスタに付く(同一著者集合+正規化題) | ★最多(月次cm101) |
| 2 | `existing_author_new_series` | 新ISBN、新クラスタ、著者は master に在 | 中 |
| 3 | `new_author_new_series` | 新ISBN、新クラスタ、著者が master に無 | 中 |
| 4 | `new_edition` | 新ISBN、既存作品の別版(文庫/完全版/新装版) | 少 |
| 5 | `correction` | **既存ISBN**の内容変化(dateModified/題/kana/ISBN訂正) | 少だが見逃し危険 |
| 6 | `retro_volume` | 取込もれ巻(欠け/末尾)を sweep が発見 | 種4領域 |
| 7 | `status_change` | 連載中→完結(最終巻signal) | 少 |
| 8 | `merge_split_fix` | 本来束ねる/分けるべき記録(再クラスタ) | ★最危険 |
| 9 | `availability` | 絶版/重版/版元変更 | 将来 |

> 型1の隠れた罠 = **虚構推理 vol23 型**(別MADB-ID+別ISBNでの再登録が別クラスタに落ちて二重ページ)。型1は「正しいページに付いたか」のクラスタ整合チェックが必須(§3 T1)。

---

## 3. 型別 必須フィールド・マトリクス(=出荷ゲートの条件)

チェックを3層に分ける:
- **T0 = スキーマ床**(loader が空だと例外。`lib/schema.ts` の min/required)。常に blocker。
- **T1 = 品質 blocker**(出すと誤り/事故。型依存)。
- **T2 = warn-hole**(出してよいが穴として追跡)。

凡例: ●=blocker / ▲=warn / 継=クラスタから継承(再導出しない) / －=不要

| フィールド/チェック | 層 | 1.新刊 | 2.既作者新作 | 3.新作者新作 | 4.新版 | 5.訂正 | 6.取込もれ巻 | 8.merge/split |
|---|---|---|---|---|---|---|---|---|
| slug 一意・規則準拠 | T0 | 継 | ● | ● | 継 | ●(安定性) | 継 | ●(+alias) |
| title / kana / romaji | T0 | 継 | ● | ● | 継 | ●変更分 | 継 | ● |
| authors[]≥1 + role | T0 | 継 | ● | ● | 継 | ▲ | 継 | ● |
| year_started / status | T0 | 継 | ● | ● | 継 | ▲ | 継 | ● |
| publisher / demographic | T0 | 継 | ● | ● | ●(版社) | ▲ | 継 | ● |
| genres[]≥1 | T0 | 継 | ● | ● | 継 | － | 継 | ● |
| editions[]≥1 / volume isbn13・number・release_date | T0 | ● | ● | ● | ● | ●変更分 | ● | ● |
| **adult_gate 実行済** | T1 | ●継/再 | ● | ● | ●(版で変) | ● | ● | ● |
| **クラスタ整合**(正しいページに付く) | T1 | ● | ● | ● | ● | ● | ● | ●最重 |
| **外部確証**(NDL/楽天/cmoa/ISBN連番) | T1 | － | － | － | ▲ | － | ●必須 | ●必須 |
| 著者 master 登録 + 読み(NDL典拠) | T1 | 継 | 継 | ●新規 | 継 | － | 継 | 継 |
| 巻番号連続性(gap/水増し) | T1 | ● | ● | ● | ● | ● | ● | ● |
| kana ↔ NDL 公式読み 整合 | T1 | 継 | ▲ | ▲ | 継 | ●変更分 | 継 | ▲ |
| synopsis | T2 | 継 | ▲ | ▲ | 継 | － | 継 | ▲ |
| cover_url | T2 | ▲ | ▲ | ▲ | ▲ | － | ▲ | ▲ |
| anilist_id 結線 | T2 | 継 | ▲ | ▲ | 継 | － | 継 | ▲ |
| magazine / catch / alt_titles.en | T2 | 継 | ▲ | ▲ | 継 | － | 継 | ▲ |

### 型ごとの要点(あなたの3パターン+α への直接回答)
- **型1 新刊**: 一番安い。新slug/kana/genre/著者は**全部継承=再導出しない**。やることは「正しいページに付く・ISBN/巻/発売日が揃う・adult再確認」。蒸留の主戦場。
- **型2 既作者新作**: ページ一式が要るが、**著者データは既知**(master参照、読み・QID済)。
- **型3 新作者新作**: 型2の全部 + **著者の新規登録**(読み=NDL典拠ID、QID試行)。一番高い。`author_data_map` の表記揺れ問題はここで NDL典拠ID を採ることで根治。
- **型5 訂正**: 変わったフィールドだけ再検証。**題/kana が変わったら slug 安定性チェック**(URL を黙って変えない=alias 必須)。ISBN が変わったらクラスタ再判定。MADB月次CSVは更新日列が無いので、**GitHub全件JSONの `dateModified` 差分**でしか拾えない(§5)。
- **型6 取込もれ巻 = 種4 の再定義**(§4)。
- **型8 merge/split**: 最高警戒。`merge_needs_external_proof` の鉄則。外部確証なしは通さない。

---

## 4. 種4 の再定義(あなたの「種4の仕様に問題」への回答)

**現状の問題**: 種4(`volumes-supplement.yml`)は「取込もれ巻の手動 yml input」。だが §3 の型6 で見える通り、取込もれ巻は**機械で発掘できる**(`_audit-volume-gaps` / `_audit-trailing-gaps` / NDL / 楽天タイトル検索 = ドラゴンボール型)。手打ちは: ①スケールしない ②provenance(根拠)が弱い ③MADB追いつき時の退役が壊れやすい。

**再定義**:
- 種4 を「手動 input」から「**取込もれ sweep の出力**」に変える。sweep が候補を出し、各候補が**マニフェストに外部確証(source)を必ず持つ**。
- 手動エントリは**真の例外のみ**(大友克洋全集のように機械で辿れないもの。`otomo_complete_works_pending`)。
- **退役の自動化**: MADB の cm101 に当該 ISBN が現れたら、マニフェストの `source` が `seed4-sweep`→`madb` に切り替わり自動 dedup(ISBN+巻番号で冪等)。今の render時ガード(種2優先)はそのまま安全網。

---

## 5. MADB と NDL を両方取る意味(あなたの問いへの回答)

役割が**相補的**で、片方では穴が空く。NDL主体は正しいが、MADB は捨てられない。

| | MADB | NDL |
|---|---|---|
| 巻レコード(cm101) | ●生きてる(月次) | ●(dcndl:volume) |
| シリーズmaster(cm104) | ✗2024-11凍結 | — |
| **成年コミックマーク** | ●**ここにしか無い** | ✗18禁を区別しない |
| 著者役割[原作]/[作画] | cm104のみ=新作で来ない | △ |
| **著者典拠ID(表記揺れ根治)** | ✗ | ●**ここにしか無い** |
| 正規化主題・版alternatives | ✗ | ● |
| 訂正検知(dateModified) | ●GitHub全件JSON | △ |

**結論**: クラスタリング・作者同定・訂正回収は**NDL主体**が現実解。ただし **成年判定だけは MADB を残す**(昨夜直したゲートの素はMADBにしか無い)。
→ 「**NDLで束ね、MADBで成年フラグと巻書誌を補う**」二層。マニフェストの `sources.cluster` に NDL典拠ID、`sources.adult` に MADB contentRating を記録して追跡可能にする。

---

## 6. マニフェストの形(=台帳の実体)

ページ(orクラスタ)単位の git追跡 seed。例:

```yaml
# data/seeds/intake-manifest/<slug>.yml  (or 1ファイルに集約)
slug: kimetsu-no-yaiba
change_type: new_volume          # この蒸留での扱い
last_intake: 2026-06-13
sources:                          # provenance = 各事実の出所
  cluster: ndl-authority:DA12345678
  adult: madb-content-rating
  kana: ndl-yomi
  synopsis: ai-anilist:101922
checks:                           # 通したチェック(verdict + 根拠)
  required_fields: pass
  adult_gate: pass(score=0)
  cluster_integrity: pass
  slug_unique: pass
  volume_sequence: pass
  kana_ndl_agree: pass
holes:                            # 既知の穴(blocker/warn)
  - {field: cover_url, severity: warn}
  - {field: synopsis,  severity: warn}
ship: true                        # ゲートの判定
```

**核心**: マニフェストは**記憶**。`checks` が「何を検証したか」、`holes` が「何が足りないか=次の作業リスト」、`sources` が「どこから来たか=再調査不要」。これが総当たり再探索を消す。

---

## 7. 段階導入(安く始めて、効く順)

- **Phase 0 = 簿記監査(最優先・安い・AIコストほぼゼロ)**
  既存66,582ページに対し、現データから型を分類し、holes と provenance を**後追いで埋める**。これで初めて「どのページに何が欠けているか」の全体像が出る。`adult` 判定スイープ([[adult-judgment-architecture]] v3)と相乗りで「乗せるべき取りこぼし」も浮く。
- **Phase 1 = 出荷ゲートを promote / slug-apply に配線**
  blocker-hole があれば本番に出さない(`.hold` サイドカー退避=`.adult` と同方式)。**これが昨夜の成年漏れを止める恒久策**。
- **Phase 2 = 型分類器を入口に**
  incoming(GitHub全件JSON差分 + 月次CSV)を本番現状と照合し型を付与。型別にゲート条件を切替。
- **Phase 3 = NDL典拠クラスタリング + 種4-as-sweep**
  クラスタキーを NDL著者典拠IDに。種4を sweep 出力化。

> 頻度(毎日 vs 月次)の議論は Phase 2 以降。**まず Phase 0-1(台帳+ゲート)を入れるのが、ship-first と総当たりの両方を同時に潰す最短路**。

---

## 7.5 現状の配線監査(2026-06-13 コードレビュー = Phase1の素地)

成年漏れ(2,233頁)の構造を解明し、 全フィルタの「配線済み/未配線」を実測。

**本番ページ集合の決まり方**: `data/manga`(SRC_DIR)が本番集合を決め、 それを作るのは
`_slug-apply-prep.py`→`_slug-apply-build.py` **のみ**。 promote は data/manga を信頼して
emit するだけ。 = **除外は2層**:
- 層1(slug-apply-prep/build): 成年ゲート(2026-06-13追加) / drop-keys(c3外国孤児/partial外れ値/NDL junk/c1外国版) / recluster元 / c2-merge。
- 層2(promote main loop): title-prefix/contains drop / subtitle drop / 雑誌(cm105) / 非漫画(外国版) / 画集 / spinoff-old / **成年ネット(2026-06-13追加)**。

**配線監査の結論**:
| フィルタ/監査 | 出力 | 本番経路に配線? |
|---|---|---|
| 成年(adult_score) | db series列 | ✅ 層1ゲート + ✅ 層2ネット(2026-06-13に二重化。 以前は**どちらにも無く漏れた**) |
| 外国版(foreign-editions) | non-manga-drop.yml | ✅ promote |
| 非漫画/雑誌/画集 | seed各種 | ✅ promote |
| page-dedup | page-dedup.yml | ✅ promote |
| フリガナ補正(NDL) | furigana-corrections.yml | ✅ promote |
| 巻番号水増し是正 | (promote内) | ✅ promote `_fix_complete_sequence_numbers` |
| AniList誤リンク | anilist-link-overrides.yml | ✅ enrich builder(2026-06-13追加) |
| coverage / 巻番号異常検出 / trailing-gaps | report | ⚪ 監視のみ(設計通り。 種4は手動領域) |

**残る本質的リスク = 「配線」でなく「シグナル」**:
- ★ゲートは `adult_score` の精度どまり。 **IDコミックス Lake/Rex 等のサブレーベルが
  adult-imprints.yml に無い**=score が立たない=二重ゲートをすり抜ける。 → 修正は**ゲート
  でなく adult_score を作る側**([[adult-judgment-architecture]] v3: 楽天不在/作者伝播/
  サブレーベル粒度)。 配線は塞いだ、 次は信号源。
- ★蒸留差分基盤(`_diff-madb.ts` 等)未実装(§5)。 = 月次蒸留の入口がまだ手動。

**Phase1 の必須チェック(この監査から確定)**: 出荷ゲートは最低限 ①adult_score>=3 ②クラスタ
整合 ③巻番号連続性 ④slug一意 ⑤T0スキーマ床 を全emission経路で検証。 今回 promote に成年
ネットを足したのは、 この「全emission経路で検証」の第一歩。

## 8. 未決(ユーザ裁定 or 月曜議論)
- マニフェストの粒度: ページ単位 vs クラスタ単位 vs 1集約ファイル(33MB freeze 回避との兼ね合い)。
- Phase 0 をいつ着手するか(楽天収穫完走後が adult/cover/release_date の素材が揃って得)。
- 型8 merge/split の確証ソース優先順位(NDL連番 > cmoa > 楽天 > Wiki?)。
- 関連: [[merge-needs-external-proof]] [[clustering-unit-is-series]] [[madb-cm104-frozen]] [[madb-data-acquisition]] [[author-data-map]] [[feedback-complete-data-before-ship]]
