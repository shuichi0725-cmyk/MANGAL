# MANGAL Project Memory

> このファイルは Claude Code session の context bootstrap 用。新しいセッションを開始したら最初に読むこと。

最終更新: 2026-05-22 (a-miss fill **完全消化** = qid: 26 + name: 14 = 40 件 直接 fill 完了、 a-miss 合計 0 件)

---

# 2026-05-22 セッション 18: Phase 0 完了 (= a-miss 残務 + safety check)

## TL;DR

- **a-miss qid: 26 件 fill 完了** (= commit `5456a69`) — PUA / smart-quote / special-chars 混入で過去 skip された entries を Python 経由で直接 fill
- **a-miss name: 14 件 fill 完了** (= commit 本セッション) — name: prefix 残務 (実数値、 後述 bug 参照)
- **a-miss 合計 残り = 0 件 ✅** (= en filled 40,990 / 76,435 = 53.63%)
- **typecheck + vitest 緑** (= 7 files / 209 tests pass、 lib/seed3.ts v1/v2 union schema 安全動作確認)
- **state check script の bug 発見 + 修正** (= 次節)

## state check script の bug (= 1,699 件 と誤 count していた件)

旧 logic (= MEMORY.md セッション 17 の Step 2 に記載):
```python
title = next((p[5:] for p in parts if p.startswith('name:')), '')  # ← FIRST = creator!
```

`name:` prefix entries の key format は `name:<creator>|name:<title>` (= 必ず 2 parts)。
旧 logic では **最初の** name: field = **creator 名** を title と誤認識して katakana 判定 →
creator がカタカナ含む entries (= 「azuタロウ」 等) を a-miss 対象と誤 count。

修正 logic:
```python
name_parts = [p[5:] for p in parts if p.startswith('name:')]
title = name_parts[-1] if name_parts else ''  # ← LAST = actual title
```

この修正で 旧 count 1,699 → 実数値 14 件 と判明、 即 fill して 0 件達成。

## 種2 / 種3 v2 の キー一覧資料 を生成

- `scripts/_build-schema-doc.py` → `docs/schema-reference.html` (= A4 縦印刷向け、 commit `74ea092`)
- 種2 18 tables + 種3 10 fields の キー名 / 型 / 日本語説明 / サンプル値 / 充足率 を一覧化
- 主要 table は ONE PIECE 系列の実 data で sample 統一

## 次セッション候補 (= Phase 1 以降)

a-miss fill が完全消化したので、 次は **Phase 1 = 本番出力 + 視覚確認**:
1. `scripts/_promote-bulk-v2.py` を 全件実行 → `data/manga/<slug>/index.yml` を 大規模生成
2. 生成結果の sanity check (= slug 重複 / ローマ字 slug 漏れ / カウント)
3. frontend deploy + 主要作品の表示確認

それ以降は Phase 2 (= 残 queue 23,617 fill) / Phase 3 (= 月次蒸留 protocol 実装) を 状況に応じて。

---

# 2026-05-22 セッション 1-17: 種3 a-miss fill 全 285 batch 完了 (= 28,500 件 fill)

## TL;DR (= 次セッション 8 行サマリ)

- **a-miss 全 batch (= 1-285) fill 完了**: 17 セッションで 約 28,500 entries の `alternative_titles.en` を Opus 4.7 直筆 fill。 全 commit + push 済 (= `claude/manga-database-affiliate-3x0ms` branch)
- **現在の seed3 状態**: 76,435 entries 中 en filled = **40,950 (54%)**、 en missing = **35,485 (46%)**
- **a-miss 残り (= カタカナ含む title で en 無し) = 1,725 件**
  - 内訳 1: **qid: prefix = 26 件** (= 過去 17 セッションで 異常キーによりスキップ、 手動修復対象)
  - 内訳 2: **name: prefix = 1,699 件** (= mangaka に Wikidata QID 無し、 a-miss 抽出対象外だった group)
- **次セッションでの作業候補** (= ユーザに確認):
  - (A) qid: 26 件の異常キー 手動修復 (= 即着手可能、 小規模)
  - (B) name: 1,699 件の fill (= 17 batch 新規生成 + 17 セッション相当の作業)
  - (C) 別タスク (= 月次蒸留 / promote-bulk-v2 全件 / deploy 視覚確認 等)

## 作業の構造 (= 完全 protocol)

### Pipeline 全体

```
1. .cache/amiss/input-NNN.json (= 100 entries/batch、 list of {title, key})
   ↓
2. AI fill (= Opus 4.7 が key → {"alternative_titles": {"en": "..."}}) を生成)
   ↓
3. data/seeds/_fills/amiss-NNN.json (= dict 形式 JSON、 100 entries/batch)
   ↓
4. npx tsx scripts/_apply-fills.ts data/seeds/_fills/amiss-NNN.json
   ↓ [apply] existing: 76435, fills: 100
   ↓ [apply] done: applied=N, missing=M, total entries=76435
5. data/seeds/series-supplement-v2.yml が更新 (= 既存 entry に en field 追加)
   ↓
6. git add + commit + push (= ユーザが artifact を即取得)
```

### 1 セッションでの作業量

- **2000 件 = 20 batch = 4 parallel agents × 5 batch each**
- 各 agent は input-NNN.json を読み、 Python json.dump(ensure_ascii=False) で amiss-NNN.json を書き出す
- 全 20 batch を 一括 apply (= sequential for ループ)
- 1 commit (= 20 fill files + series-supplement-v2.yml の diff) で push

### Fill 規則 (= agent への prompt 仕様)

```
1. 公式英題が存在する → それを使う (e.g. ドラえもん → "Doraemon")
2. カタカナ外来語 title → 元の言語に back-transliterate (e.g. バトル → "Battle")
3. シリーズ variant/spinoff → 親シリーズ英題 + 説明的 subtitle
4. 公式英題なし日本オリジナル → Hepburn romaji
5. en field は **必ず非空文字列**
```

## 各セッションの実績 (= 全 17 セッション履歴)

| Session | Batches | Entries | Applied | Missing | Commit |
|---------|---------|---------|---------|---------|--------|
| 1-11 | 003-180 | ~18,000 | ~18,000 | ~数件 | 372eb08...6499918 |
| 12 | 181-200 | 2000 | 1999 | 1 (WORKING!!Re anomalous) | 121a2d4 |
| 13 | 201-220 | 2000 | 1997 | 3 (Tezuka, IDOLiSH7, キャンディキャンディ) | bcfa46f |
| 14 | 221-240 | 2000 | 1999 | 1 (ドッグデイズ) | 74a5480 |
| 15 | 241-260 | 2000 | 1997 | 3 (244,255,258 leading-quote) | f8581d8 |
| 16 | 261-280 | 2000 | 2000 | 0 (281-280 99 entries due to duplicate key in input) | 71f29e5 |
| 17 | 281-285 | 424 | 423 | 1 (隠れビッチ smart-quote) | 2aacb15 |

**累計**: 28,500 entries 処理、 約 28,470 件 apply 成功、 約 30 件異常キーで skip。

## 残り a-miss 1,725 件の詳細

### Category A: qid: prefix の異常キー (= 26 件、 直接 fill 対象)

過去 17 セッションで apply スキップされた entries。 全て手動対処可能。 異常パターン:

```
1. leading double-quote in key (= 12 件):
   "qid:Q193300|name:やじうまマーチ|sub:手塚治虫学年誌傑作集 : 完全限定版""
   "qid:Q232660|name:アイドリッシュセブンre: member""
   "qid:Q4348970|name:ドッグデイズ|sub:銀牙少年伝説 : ロクとボクの一番熱かった日々"
   "qid:Q48762211|name:愛とエロスの日本近代文学史|sub:..."
   "qid:Q617888|name:ヤスダスズヒト画集 シューティングスター・カルナバルside: 夜桜四重奏"
   "qid:Q6455305|name:ギャグマンガ日和&ギャグマンガ日和GB|sub:..."
   (他 6 件)

2. smart-quote (= U+201C/U+201D) in key (= 例 1 件):
   qid:Q96127776|name:"隠れビッチ"やってました。 (= スマートクォート)

3. その他 colon / special char 異常 (= 残り 13 件):
   ウルフチックにお願い、 パニックパラダイス、 食戟のソーマL'etoile、
   アウターゾーン リ: ビジテッド、 スター・ウォーズ: マンダロリアン、
   わがままレイディ、 猫と月チェイス、 アレが生えてre: start!、
   この愛は、異端。: ベリアル文書、 アラサーバツイチ女が魔性の猫の愛人に...、
   にゃんにゃんドリーム、 "Good Boy!"ガウディ、 プラスティック: ベイビイズ、
   バージンラブ、 西村しのぶの神戸・元町"下山手ドレス"、 いずみタッチダウン!、
   キャンディキャンディ (= seed にキー無し anomaly)、
   魔法少女リリカルなのはA's PORTABLE -THE GEARS OF DESTINY-マテリアル娘。 ダッシュ (= 重複)
```

### Category B: name: prefix entries (= 1,699 件、 別 batch 必要)

これらは mangaka に Wikidata QID が無い series。 過去の `.cache/amiss/input-*.json` 抽出時に **対象外** だった (= qid: prefix のみ抽出)。

サンプル (= 多くは作者名そのもの、 タイトルではない):
```
azuタロウ、 Dr.モロー＆スタジオ寿、 Eve音楽アーティスト、
Guy・Jeans、 LINEマンガ、 アイディアファクトリー (× 3)、
あーもんど (× 2)、 アオイ、 アオエナ、 アカコッコ、 ...
```

**注意**: これら 1,699 件には 「mangaka 名そのもの」 が key の `name:` field に入っている パターン (= タイトル不在) も含まれており、 fill 対象として適切かは別途判定要 (= mangaka name は en filling 対象として無意味)。

## 次セッションでの再開手順

### Step 1: 状態確認 (= 最初 30 秒)

```bash
cd /home/user/MANGAL
git pull origin claude/manga-database-affiliate-3x0ms
git status   # clean のはず
git log --oneline -5   # 2aacb15 が最新のはず
```

### Step 2: 残り a-miss 件数の再確認

```bash
python3 << 'EOF'
import yaml, re
with open('data/seeds/series-supplement-v2.yml') as f:
    doc = yaml.safe_load(f)
KATAKANA = re.compile(r'[゠-ヿ]')
qid_remaining = []
name_remaining = []
for e in doc['series']:
    key = e.get('key', '')
    parts = key.split('|')
    title = next((p[5:] for p in parts if p.startswith('name:')), '')
    en = (e.get('alternative_titles') or {}).get('en') or ''
    if KATAKANA.search(title) and not en:
        if key.startswith('qid:'): qid_remaining.append((key, title))
        elif key.startswith('name:'): name_remaining.append((key, title))
print(f'qid: 残り {len(qid_remaining)} 件')
print(f'name: 残り {len(name_remaining)} 件')
EOF
```

期待値: `qid: 残り 26 件 / name: 残り 1,699 件` (= 月次蒸留や種3 追加が無ければ不変)

### Step 3: ユーザに作業方針を聞く

「現状は a-miss 1,725 件残り (qid: 26、 name: 1,699)。 どれから着手しますか?」
- (A) qid: 26 件の手動 fill (= 即終了)
- (B) name: 1,699 件 fill 用 batch 再生成 + 17 batch fill (= 約 17 セッション)
- (C) 別タスク (= 月次蒸留 / promote-bulk-v2 / deploy 視覚確認 等)

### Step 4-A: qid: 26 件処理の手順

```bash
# 1. 残り qid: 異常キー 26 件を 直接 JSON で書き出す
python3 << 'EOF'
import yaml, re, json
with open('data/seeds/series-supplement-v2.yml') as f:
    doc = yaml.safe_load(f)
KATAKANA = re.compile(r'[゠-ヿ]')
fills = {}
for e in doc['series']:
    key = e.get('key', '')
    if not key.startswith('qid:'): continue
    parts = key.split('|')
    title = next((p[5:] for p in parts if p.startswith('name:')), '')
    en = (e.get('alternative_titles') or {}).get('en') or ''
    if KATAKANA.search(title) and not en:
        fills[key] = {"alternative_titles": {"en": ""}}  # 各 title を Opus 直筆で埋める
# data/seeds/_fills/amiss-fix-qid.json に書き出し
EOF

# 2. 各 title に対し Opus が en を入力 (= 26 件、 1 prompt で全部済む)
# 3. apply: npx tsx scripts/_apply-fills.ts data/seeds/_fills/amiss-fix-qid.json
# 4. commit + push
```

注意: 一部の key (= leading quote 等) は seed の キー自体が壊れている可能性、 その場合は seed 側の キー訂正が必要 (= 種3 既存破壊 にあたるため ⚠️ Go サイン 必要)。

### Step 4-B: name: 1,699 件処理の手順

```bash
# 1. a-miss 抽出 script を 改修して name: prefix も対象に追加
# (= 元の抽出 script を要調査、 .cache/amiss/input-*.json を生成する script)
# 2. .cache/amiss/input-286.json 以降を新規生成 (= 17 batch = 1,699 件)
# 3. 通常通り 4 parallel agent で fill 生成 + apply
# 4. 1 セッション = 2000 件想定だが、 残り 1,699 件なので 1 セッションで全完了可能
```

⚠️ **未確認**: 「.cache/amiss/input-*.json を生成した script は どこにあるか」 — `ls scripts/_select-* scripts/_extract-amiss*` で見つからなかった。 過去のセッション (= session 1-11) で生成された pre-existing file の可能性。 次セッションで `git log -- scripts/ .cache/amiss/` で 履歴確認推奨。

## 重要ファイル一覧

```
data/seeds/series-supplement-v2.yml         # 種3 v2 本体 (76,435 entries)
data/seeds/_fills/amiss-NNN.json            # batch 003-285 (= 285 fill files)
.cache/amiss/input-NNN.json                 # batch input (= 285 input files)
scripts/_apply-fills.ts                     # 汎用 apply runner (= 既存利用)
lib/seed3.ts                                # Seed3 schema 定義 (= load/write)
CLAUDE.md                                   # protocol 定義 (= 毎セッション自動読み込み)
MEMORY.md                                   # このファイル
```

## 重要な protocol 遵守事項 (= CLAUDE.md 参照)

- **branch**: `claude/manga-database-affiliate-3x0ms` 固定
- **commit 時 push までセット**: ユーザが artifact を即取得できるよう
- **既存破壊禁止**: 種3 既存 entry の上書き/削除/編集は禁止 (= 純粋追加 only)
- **abort 条件**: 既存 key の content が変わった / typecheck red 等
- **2000 件づつ終わったらセッション終了**: ユーザ次の指示待ち

## 既知の anomaly パターン (= 次回 fill で再発の可能性)

1. **leading double-quote in JSON key** — Python json.dump で `ensure_ascii=False` 利用時、 key 内の特殊文字で 発生
2. **smart-quote (U+201C/U+201D)** in key — 日本語 IME 由来
3. **duplicate key in input file** — input-280 で 1 件発生 (= 元 data 重複)
4. **seed key mismatch** — key は input に存在するが seed の YAML には存在しない (= input 抽出時の glitch?)
5. **special chars (`:` , `'` , `&`, `"` 等)** — colon + space 等で key parse 異常

これらは いずれも `missing=N` で report され、 apply は止まらない (= 残りは正常 apply)。

---

# 2026-05-18 セッション: 種3-v2 top 2000 fill (= B2 完了) + 種2/種3 v2 体系の整理

## TL;DR (= 次セッション 5 行サマリ)

- **種2 = `.cache/db-v2.sqlite`** (= path B' rebuild、 series 158,263 / editions 多数 / volumes 多数)、 旧 `.cache/db.sqlite` は触らない
- **種3 = `data/seeds/series-supplement-v2.yml`** (= schema_version 2、 現在 **52,825 entries**)。 旧 `data/seeds/series-supplement.yml` (= 70,202 entries) と **完全 disjoint**、 別物として共存
- **B2 (= top 2000 AI fill) 完了**: 累計 batch 706-725 で queue[0:2000] を Opus 4.7 直筆 fill。 全 `applied=100, missing=0` 確認、 commit + push 済 (= 21 commits)
- **残課題**: queue 残り **23,617 entries** (= 順位 2001-25617) が未 fill。 これは次回以降。 また promote-bulk-v2 で実 yaml 出力 + frontend 視覚確認 もまだ
- **`/ultrareview` 注意**: B2 完了 commit の deploy / vitest / typecheck がまだ通っているか未確認 (= 次セッション最初に `npm run typecheck && npm test` で safety check 推奨)

## 種2 / 種3 (v2 系) の確定整理 (= 2026-05-17~18 path B' 経由の最新版)

### 種2 v2 = `.cache/db-v2.sqlite` (= 158,263 series)

旧 `.cache/db.sqlite` (= 70,202 series、 構造的 bug あり) は **完全に不変** のまま並走、 v2 は別ファイル。
schema は `db/schema-v2.sql`、 19 tables。 生成 pipeline (= 直列実行):

```
1. scripts/_build-series-v2.py    (= 種1 → .cache/series-v2.json、 158,263 clusters)
2. scripts/_db-init-v2.py         (= db-v2.sqlite を空 schema で初期化、 master を seed)
3. scripts/_populate-v2.py        (= cluster → db-v2.sqlite に投入、 巻号 parse 等)
4. scripts/_apply-adult-filter-v2.py (= adult signal 5 で skip)
5. scripts/_promote-bulk-v2.py    (= db-v2 → data/manga/<slug>/index.yml に書き出し)
6. scripts/_extract-top-completed.py (= 主要完結作品 top N 抽出、 試験用)
7. scripts/_scan-anomaly.py       (= I1-I6 anomaly 検出)
8. scripts/_backfill-title-kana-v2.py (= madb-enrich.json から title_kana 補完、 90.1% 救出)
```

**重要設定値** (= 2026-05-18 時点):

```python
# scripts/_promote-bulk-v2.py
KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
DROP_IMPRINT_PATTERNS = ["My first big", "コンビニ", "増刊", "同人", "ジャンプremix", "フィルムコミック", "カッパ・ノベル", "カッパ・ホーム"]
DROP_IMPRINT_LOWER_PATTERNS = ["bilingual", "english"]
DROP_IMPRINT_LOWER_PATTERNS_NO_EQ = ["complete works"]  # 「=」並列除外
DROP_TITLE_PREFIX_PATTERNS = ["テレビアニメ版", "TVアニメ版", "アニメコミック", "劇場版", "映画", "OVA", "ノベライズ", "ノベル"]
DROP_TITLE_CONTAINS_PATTERNS = [34 patterns]  # ガイドブック / ファンブック / 設定資料集 等 (= 詳細 CLAUDE.md 参照)
CUTOFF_YEAR = 2015  # spinoff で この年以降なら keep
```

### 種3 v2 = `data/seeds/series-supplement-v2.yml`

- `schema_version: 2`、 `generator: claude-opus-4-7-direct-fill`
- 現在 **52,825 entries** (= 50,825 placeholder + top 2000 fill = batch 706-725)
- 旧 `data/seeds/series-supplement.yml` (= schema_version 1、 70,202 entries) と **disjoint** = key 重複 0、 別物として共存
- schema 定義: `lib/seed3.ts` (= `schema_version: z.union([z.literal(1), z.literal(2)])` で v1/v2 両対応)
- default path も lib/seed3.ts で `data/seeds/series-supplement-v2.yml` に切替済
- Seed3EntrySchema は v1 と互換 + `alternative_titles.{en,fr,de,it,pt}` optional 追加

### 種3 v2 各 entry の fill schema (= 種3 旧と互換 + 拡張)

```json
{
  "<key>": {
    "magazine": "weekly-shonen-jump" or null,        # magazines.yml の key、 不明時 null
    "demographic": "shounen|shoujo|seinen|josei|kodomo|other",
    "genres": ["action", "adventure"],                # 1-4 tag、 master keys は genres.yml
    "synopsis": "80-200 char の独自要約",
    "status": "ongoing|completed|hiatus",
    "anime_adapted": true|false,
    "alternative_titles": {"en": "One Piece"}        # 外来語 title では ⚠️必須 fill (= 漏れると slug rename 困難)
  }
}
```

- **key**: `(qid + baseTitle)` 複合 ID。 qid 無し series は `name:<creator>|name:<title>` 形式
- **slug 命名規則** は CLAUDE.md 参照 (= ふりがな判定 + 数字読み判定 + alt_en 優先)
- **alternative_titles.en** は ⚠️ **外来語起源 title (= 「ワンピース」「ブリーチ」「アイシールド21」「ドラゴンボール」 等) に必須 fill** — これで slug 生成が `wanpiisu` ではなく `one-piece` になる。 fill 漏れすると `wanpiisu.yml` / `aishiirudo-21.yml` のような ローマ字 slug が生成され、 **後から rename 困難** (= URL 互換性 / backup / 外部参照に影響)。 fill 時の判定基準: カタカナ含む外来語起源 (= 英語 / 独語 / 仏語 / 西語 から音写) なら必須
- **genres** は CLAUDE.md の 「genres 規約」 参照 (= sports は包括タグ、 baseball / soccer のみ併用サブタグ、 他スポーツはサブ分類しない)

### B2 完了状態 (= 2026-05-18 23:43 JST 達成)

| Item | Value |
|---|---|
| Queue 全体 (= `data/seeds/_ai-fill-queue.yml`) | 25,617 entries (= isbn ≥ 2 threshold) |
| B2 = top 2000 fill 完了 | batch 706-725 = 20 batches |
| 各 batch 結果 | 全件 `applied=100, missing=0` |
| commits | 21 (= 20 batch + 1 PUA fix) |
| 残 queue | 23,617 entries (= rank 2001-25617、 isbn ≥ 2 だが未 fill) |
| 種3 v2 file size | 52,825 entries (= 50,825 placeholder + 2000 fill) |
| JST 進捗報告 | 22:19 (500件), 22:48 (1000件), 23:16 (1500件), 23:43 (2000件) |

**batch 706-725 で fill した主要シリーズ** (= sample):
- 鬼平犯科帳 (329 ISBN)、 美味しんぼ (244)、 キン肉マン、 ONE PIECE、 ジョジョ、 BLEACH、 DEATH NOTE
- バクマン、 進撃の巨人、 NARUTO、 はじめの一歩、 ドラゴンボール、 名探偵コナン
- なろう系 (= 転スラ / オーバーロード / リゼロ / 八男 / ナイツマ 等)
- 競馬 / ボクシング / ヤンキー / グルメ等の中堅作品

## 蒸留 protocol の更新 (= 2026-05-18 現在の正)

### 月次蒸留 protocol (= CLAUDE.md 登録済、 触らない)

CLAUDE.md に既に登録済の月次蒸留 protocol は **大原則不変**:
- ユーザ 「月次蒸留して」 (= 完全一致) で起動
- 種1 / 種2 / 種3 は壊さない (= 純粋追加 only)
- Phase 0 前提確認 → Phase 1 差分 report + Go サイン待ち → Phase 2 実行

### 蒸留が現在指す「種2 / 種3」 の対応関係

CLAUDE.md の protocol 文面は **v1 系の path 名で書かれている** (= `.cache/db.sqlite` / `data/seeds/series-supplement.yml`)。 実体は path B' 移行後 **v2 系を指すべき** (= `.cache/db-v2.sqlite` / `data/seeds/series-supplement-v2.yml`)。

**次セッションで CLAUDE.md の以下を v2 path に書き換える宿題**:

| CLAUDE.md 内 旧 path | 真の現役 path |
|---|---|
| `.cache/db.sqlite` | `.cache/db-v2.sqlite` |
| `data/seeds/series-supplement.yml` | `data/seeds/series-supplement-v2.yml` |
| `scripts/_diff-series.ts` | path B' では `scripts/_build-series-v2.py` の incremental 化として再設計が必要 |
| `scripts/_select-supplement-diff.ts` | v2 で同等の placeholder 抽出 (= synopsis 不在 entry list 化) |

ただしユーザの「壊すな」 protocol が最優先なので、 v2 path に書き換える前に **必ずユーザ確認** を取ること。

### 蒸留 Phase 2 (実行) の AI fill loop は本セッション B2 で確立した protocol を踏襲

= 「種3 fill 作り方 (= 再利用 guide / 月次蒸留 & 新規シリーズ追加時)」 セクション (= MEMORY.md 末尾) に書いてある手順を **そのまま流用**。 v2 用に default path だけ書き換え:

```bash
# v2 系での適用 (= 2026-05-18 以降)
npx tsx scripts/_apply-fills.ts data/seeds/_fills/batch-NNN.json
# → 既定で series-supplement-v2.yml に適用 (= lib/seed3.ts の DEFAULT_PATH)
# 期待: applied=N, missing=0, total entries=52825 (= 種3 v2 現在 size)
```

batch JSON 形式 (dict) は v1 と同一、 ただし key は v2 では qid 形式と name: 形式が混在 (= 旧種3 は qid 形式のみだった)。

## 未解決の課題 (= 次セッション で 続行) — 重要度順

### 🔴 重要 (= 早めに着手)

1. **種3 v2 queue 残 23,617 entries の fill** (= ISBN 巻数 1 = 中堅 / マイナー作品)
   - 現状 top 2000 (= rank 1-2000) は B2 で fill 済 → 99.7% カバレッジを目指すなら残全部
   - 作業量: 25,617 - 2,000 = 23,617 entries → 100/batch なら 236 batches
   - cost 概算: Opus 4.7 直筆 fill は 2 時間 / 2000 件 ペースなので 236 batches なら ~24 時間 (= 複数セッション要)
   - 着手判断はユーザに確認 (= 「優先度低でいい」 / 「順次進めて」 / 「promote-bulk 動作確認が先」 等)

2. **promote-bulk-v2 で実 yaml 出力 + frontend 視覚確認**
   - 現在 種2 v2 + 種3 v2 が揃ったが、 promote-bulk-v2 が実 yaml 出力したか? 出力済 47 yml は **古い**(B2 fill 前) ので **再生成必要**
   - `scripts/_promote-bulk-v2.py` を v2 種3 でもう一度 run → `data/manga/<slug>/index.yml` 再生成
   - その後 frontend を deploy + 視覚確認 (= 鬼平犯科帳 / 美味しんぼ / ONE PIECE / ジョジョ の表示確認、 magazine/synopsis 等の v2 種3 fill が反映されてるか)

3. **typecheck / vitest 確認**
   - B2 commit 群で `lib/seed3.ts` を `z.union([z.literal(1), z.literal(2)])` に変更している
   - 次セッション最初に `npm run typecheck && npm test` で safety check (= 想定外の breakage が無いか)

### 🟡 中程度

4. **CLAUDE.md の v1 → v2 path 書き換え** (= 上記蒸留 protocol セクション参照)
   - ユーザに「v2 path に書き換えていい?」 確認後実施
   - 月次蒸留 protocol の Phase 0 で参照する path を v2 に揃える

5. **`scripts/_diff-series.ts` / `_select-supplement-diff.ts` / `_diff-madb.ts` が未実装**
   - 月次蒸留 protocol Phase 0 でこれらの存在 check があるので、 実装するまでは「月次蒸留して」 を投げると abort される (= 安全側、 想定通り)
   - 実装の優先度は低 (= 月次蒸留する前まで)

6. **anomaly I1-I6 残**
   - I1 巻号飛び、 I2 edition多、 I4 期間矛盾 (= 0 件)、 I6 label残 (= 43 件)
   - `scripts/_scan-anomaly.py` を v2 種3 反映後に再 run して状況把握

### 🟢 低

7. **mezon-ikkoku / doragon-booru の year_ended 過剰** (= 旧 MEMORY.md 課題 #1)
   - v2 種3 の `status: completed` で救えるなら解決可
   - per-vol 初版 MAX cutoff は実装済 (= 2026-05-17)

8. **creator merge logic 未実装** (= 旧 MEMORY.md 課題 #3)
   - 「鬼平犯科帳」 が 4 cluster (= 池波正太郎 / さいとう・たかを 等) になる
   - B2 で同一 base title の複数 cluster を別々に fill しているので、 merge logic 実装は後回し可

9. **`/ultrareview` を B2 完了 push に対して走らせる**
   - もしユーザが望むなら、 21 commits の品質を確認

### ⚪ 設計

10. **旧 種3 (= series-supplement.yml、 70,202 entries) の扱い**
    - v1 系で 100% fill 済、 v2 系と完全 disjoint
    - 月次蒸留で v1 系を引退する判断は未定 (= ユーザ確認要)
    - 現状 frontend は 種3 v1 を参照しているはず (= 確認要)

## ⚠️ 次セッション 開始時の必読 / 必実行

1. **このセクション (= MEMORY.md 冒頭の 2026-05-18 section) を熟読**
2. CLAUDE.md 全文読了 (= 自動)
3. `git pull origin claude/manga-database-affiliate-3x0ms` で最新取得 (= B2 commit 群)
4. `git log --oneline -25` で B2 commit (= batch 706-725) を確認
5. `wc -l data/seeds/series-supplement-v2.yml` で 種3 v2 size が 52,825 entries であることを確認
6. `npm run typecheck && npm test` で safety check (= B2 で lib/seed3.ts 変更してるので)
7. ユーザに優先順位を聞く:
   - 「B2 残 23,617 entries の続き fill 進める?」
   - 「promote-bulk-v2 再 run + 視覚確認 進める?」
   - 「別作業 (= CLAUDE.md v2 化 / 月次蒸留 script 実装 / 旧 yaml クリーンアップ) 進める?」

## 関連 commit (= 本セッション = B2 完了)

```
d89438d  data(seed3): batch 725 fix PUA char + reformat
d153246  data(seed3): batch 725 (= entries 1901-2000) Opus 4.7 直筆 fill - B2 完了 2000/2000
a9649a3  data(seed3): batch 724 (= entries 1801-1900) Opus 4.7 直筆 fill
493451a  data(seed3): batch 723 (= entries 1701-1800) Opus 4.7 直筆 fill
79db437  data(seed3): batch 722 (= entries 1601-1700) Opus 4.7 直筆 fill
d8a5110  data(seed3): batch 721 (= entries 1501-1600) Opus 4.7 直筆 fill
ce2dff0  data(seed3): batch 720 (= entries 1401-1500) Opus 4.7 直筆 fill
0a68ddd  data(seed3): batch 719 (= entries 1301-1400) Opus 4.7 直筆 fill
adaad92  data(seed3): batch 718 (= entries 1201-1300) Opus 4.7 直筆 fill
91e0255  data(seed3): batch 717 (= entries 1101-1200) Opus 4.7 直筆 fill
6c64d56  data(seed3): batch 716 (= entries 1001-1100) Opus 4.7 直筆 fill
b2aca6b  data(seed3): batch 715 (= entries 901-1000) Opus 4.7 直筆 fill   [JST 22:48 = 1000件]
66bb1c4  data(seed3): batch 714 (= entries 801-900) Opus 4.7 直筆 fill
e19f054  data(seed3): batch 713 (= entries 701-800) Opus 4.7 直筆 fill
b8e6c68  data(seed3): batch 712 (= entries 601-700) Opus 4.7 直筆 fill
5b5f800  data(seed3): batch 711 (= entries 501-600) Opus 4.7 直筆 fill
4d453c7  data(seed3): batch 710 (= entries 401-500) Opus 4.7 直筆 fill   [JST 22:19 = 500件]
cb2b96b  data(seed3): batch 709 (= entries 301-400) Opus 4.7 直筆 fill
c4cd973  data(seed3): batch 708 (= entries 201-300) Opus 4.7 直筆 fill
ada10ca  data(seed3): batch 707 (= entries 101-200) Opus 4.7 直筆 fill
c0c788c  data(seed3): batch 706 (= entries 1-100) Opus 4.7 直筆 fill  (前セッション)
```

---

## プロジェクト概要

- 漫画作品の Japanese database (NDL Search ベース) + Next.js 静的 export frontend
- 最終ターゲット: Amazon アフィリエイトサイト
- 戦略原則: **Amazon カバー画像 / 価格 / 在庫のみ使用**。NDL/openBD/Rakuten 等の画像・価格は不使用 (Phase 5 で PA-API 承認後に Amazon に切替)
- 現在 Phase 4.5 相当 (DB 整備 + bulk-promote pipeline + frontend MVP + CI auto-deploy 完成)、 Phase 5 = Amazon PA-API 承認待ち

## 主要ファイル

### Backend / DB / pipeline
- `db/schema.sql`: 現行 schema_version = **7** (6 → 7: 3-state model 用に `series_archive` / `series_excluded` / `admin_audit` 追加。 詳細は最後の 2026-05-08 夜セクション)
- `scripts/promote-bulk.ts`: NDL → series/editions 自動 promote。adult 検出は `lib/adult-score.ts` 経由
- `scripts/promote-drafts.ts`: `_drafts/*.yml` のうち placeholder 0 件のものを `data/manga/*.yml` へ昇格
- `lib/adult-score.ts`: `computeAdultScore` の純関数実装 + unit test (`lib/adult-score.test.ts`)
- `lib/adult-imprints.ts`: `data/seeds/adult-imprints.yml` の Zod schema + reader (= `imprints` / `distribution_channels` / `ambiguous` / `false_positives` の 4 セクション)
- `lib/admin-state.ts`: 3-state model 操作 library (listExcluded / reinstate / permanentDelete / manualExcludeSeries / listAudit)。 全 transaction + admin_audit logging
- `lib/openbd-kana.ts`: openBD collationkey (= ヨミガナ katakana) → hiragana 変換ヘルパ + tests
- `scripts/fetch-adult-lists.ts`: JA Wikipedia から adult publishers / mangaka リスト取得 (Fix C)
- `scripts/seed-adult-imprints.ts`: yaml seed → adult_imprints テーブル INSERT (Tier 2)
- `scripts/clean-imprint-dump.ts`: raw imprint dump → adult-imprints.yml 生成 (Tier 2)
- `scripts/admin-state.ts`: 3-state CLI (= `npm run admin:state <list-excluded|counts|reinstate|delete|exclude-series|audit>`)
- `scripts/admin-server.ts`: 管理 UI server (zero-deps node:http、 Basic Auth、 server-rendered HTML、 localhost-only、 /admin/excluded + /admin/audit)
- `scripts/backfill-archive.ts`: 既存 series → series_archive 一回限り migration (= schema v7 移行用)
- `scripts/fetch-ndl.ts`, `scripts/fetch-wikidata.ts`: 既存の主要 fetcher
- `scripts/fetch-wikipedia.ts`: layer A/B/C diagnostic 入り、 magazine/genre/synopsis/kana 補完
- `scripts/fetch-openbd-bulk.ts`: title_kana のみ openBD で補完 (66% カバレッジ)
- `scripts/probe-openbd.ts`: openBD coverage 測定 (read-only diagnostic)
- `lib/edition.ts`: `normalizeCreatorName`, `matchAdultPublisher` 等の utility
- `data/seeds/_raw-imprint-dump.txt`: ユーザ提示の raw imprint→publisher dump (~339 entry)
- `data/seeds/adult-imprints.yml`: 整形済 adult imprint seed (= **235 imprints** + 14 distribution_channels + 13 ambiguous + **17 false_positives** [= probe で FP rate >=50% と判明、 DB 投入から除外])
- `data/seeds/adult-publishers-manual.yml`: 白夜書房等の manual seed (Wikipedia 抽出に出ない補完)

### Frontend (Next.js 15.5.15 + Tailwind 4.2.4)
- `app/HomeClient.tsx`: ホーム (Search + CategoryHub + FilterPanel + MangaGrid)
- `app/manga/[slug]/page.tsx`: 詳細ページ (cover slot / メタ / synopsis / 受賞歴 / VolumeRow / Wikidata link)
- `components/CategoryHub.tsx`: ホーム top の 12 タイル grid (種類 4 + 分野 4 + 並び順 4)
- `components/MangaCard.tsx`, `MangaGrid.tsx`: ホーム 1 列縦リスト
- `components/VolumeTile.tsx`, `VolumeRow.tsx`: 巻一覧 (横並び flex、 cover slot 左 / メタ右)
- `components/FilterPanel.tsx`: 種類 / 連載状態 / 並び順 / 出版年 / 出版社 / 連載誌 / 著者 / ジャンル
- `components/CoverImage.tsx`: src=null 時 null 返却 (= placeholder 廃止、 親側で conditional 描画)
- `components/SearchBox.tsx`, `AffiliateLink.tsx`
- `lib/loadData.ts`: `loadAllManga()` で yaml + master を全件 load
- `lib/schema.ts`: MangaSchema (title_kana / authors / publisher / magazine / demographic / genres / synopsis / **anime_adapted / anime_first_year / alternative_titles / awards / wikidata_qid** / editions). VolumeSchema に **kindle_asin / description** 追加。 schema 拡張は全 optional (= 既存 yaml 不変で互換)
- `lib/filters.ts`: FilterState (query, yearMin/Max, demographics, publishers, magazines, authors, genres, **anime, hasAwards, statuses, sort**) + applyFilters + sortItems + filtersFromSearchParams (URL → state、 URL = source of truth)
- `lib/format.ts`, `lib/romaji.ts`, `lib/kana.ts`: format / 表記変換 utility
- `wrangler.jsonc`: Cloudflare Workers Assets で `out/` を配信
- `next.config.ts`: `output: "export"` 静的生成、 `unoptimized: true`

### Workflows
- `.github/workflows/bulk-promote-test.yml`: NDL fetch → wikipedia → openbd:bulk → promote → drafts quality stats → upload artifact
- `.github/workflows/deploy-cloudflare.yml`: push trigger で Next build → wrangler deploy (= CI auto-deploy、 必要 secrets: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID)

## 現在の adult 検出設計 (Fix C + Tier 1B/2, 2026-05 完成)

`lib/adult-score.ts` の `computeAdultScore` (純関数。 unit test は `lib/adult-score.test.ts` に 27 ケース) が 4 signal を additive 合算 (threshold = 3 で skip):

| Signal | Source | Weight |
|---|---|---|
| `wikidata_hentai_credit` | mangaka.has_adult_credit (Wikidata P136=Q172241) | +2 |
| `wikipedia_adult_mangaka_list` | adult_mangaka_known テーブル (Wikipedia「日本の成人向け漫画家の一覧」) | +2 |
| `adult_imprint` | adult_imprints テーブル (manga-db.com 系 dump、 **235 imprint** [= 252 から probe FP 17 件除外後]、 Tier 2) | +3 |
| `adult_publisher_imprint` | adult_publishers テーブル (Wikipedia「成人向け漫画雑誌の一覧」+ manual seed) | +3 |

Option B 設計: 作家シグナルのみ (2 or 4) では threshold に届かない/届くで線を引き、出版社/imprint シグナル (+3) は単独で確定とする。
imprint と publisher は **排他** (どちらか一方だけ発火、 imprint の方が granular なので優先)。
**`adult_score >= 3` で promote-bulk が draft skip**。試金石 run #11 (qids=Q193300 Q1121064) で:

- 唯登詩樹 ジャンクション/Uma・uma (白夜書房) → score=5 → skip ✅
- 唯登詩樹 集英社/講談社 一般作品 (Kirara, Yui shop, ボクのふたつの翼 等) → score=2 → drafted ✅
- 手塚治虫 全 13 シリーズ → score=0 → drafted ✅

`adult_publishers` は精選 21 件 (五十音/ノイズ/「○○書店」等を除外)。
Tier 1B (2026-05-06) で大手 mainstream publisher (講談社・白泉社・集英社・小学館・秋田書店・KADOKAWA・芳文社・実業之日本社・少年画報社・ぶんか社 等 22 社) を `PUBLISHER_DENY_LIST` に追加。

## 試金石 (canary) 作家

- **Q193300 = 手塚治虫**: 一般中心。false positive 検出用
- **Q1121064 = 唯登詩樹**: adult/general 混在型。mixed-portfolio 検出用 (難ケース)
- **scaling-sample-50** (`data/seed/scaling-sample-50.txt`, 2026-05-05): 6,752 名 CSV から stride 135 で 50 名 sample。 GH Actions run #25389566324 (8 分 29 秒、緑、 599 series → 233 drafts)

## scaling-sample-50 で判明した知見 (2026-05-05)

### 解消済み (Tier 1A)

- **「きい」(Q38276629) false positive**: Wikipedia 「日本の成人向け漫画家の一覧」の短名 「きい」 が我々の DB の 堀田きいち (別名「きい」) と normalize 後一致し、 君と僕。@ Square Enix Gangan を始め全 50+ シリーズに `wikipedia_adult_mangaka_list=2` を誤発火させていた (Option B のおかげで score=2 < 3 で drafted されており実害なしだが、 review 時 misleading)
- **対処**: `scripts/fetch-adult-lists.ts` の `extractAdultMangaka` で normalized 後 length < 3 を弾くよう変更。 publisher 側 (line 200) は元から `< 2` フィルタあり、これで mangaka 側も対称化。 1-2 文字の legitimate な adult-only 作家がいた場合は将来的に `data/seeds/adult-mangaka-supplement.yml` (未作成) で手動救済する前提

### 解消済み (Tier 1B + Tier 2, 2026-05-06)

- **倉科遼 / 氏賀Y太 などの adult-leaning 作家の false-negative**:
  - 原因: publisher 単位 (リイド社・辰巳出版・ぶんか社等) では adult/mainstream 二値判定不能、 真の granularity は imprint 単位 (例: クリベロン@リイド社、 ペンギンクラブ@辰巳出版、 サイベリア系@ぶんか社)
  - **対処 Tier 2**: ユーザ提示の imprint→publisher dump (~339 entry、 manga-db.com 系) を整形して 252 imprint を `data/seeds/adult-imprints.yml` に seed、 新テーブル `adult_imprints` + 新シグナル `adult_imprint` (+3) を `computeAdultScore` に追加。 imprint 単位 (granular) と publisher 単位 (coarse) は排他で発火
  - **対処 Tier 1B**: dump にゼロ件 / 0.x% 程度の大手 mainstream publisher (講談社・白泉社・集英社・小学館・秋田書店・KADOKAWA・芳文社・実業之日本社・少年画報社・ぶんか社 等 22 社) を `PUBLISHER_DENY_LIST` に追加、 publisher 単位 false-positive を抑制
  - 排他 collision (アクションコミックス: 双葉社 mainstream + 双葉社（アクションピザッツ） adult 両方共有) は `ambiguous` セクションに分離して seed には入れない (false-positive 防止)。 13 entry が ambiguous、 14 entry が distribution_channels (DLwolf18 系)

### 未解消 (将来)

- **3A (Phase 5)**: Amazon PA-API BrowseNode による direct 判定 (`amazon_metadata.is_adult_browse_node` 経由) — PA-API 承認後

## 未解決の課題 / 観察

- 唯登詩樹の成年コミックの大多数 (adultcomic.dbsearch.net 上で確認可能) は NDL に integration 漏れ → 我々の DB にも未収録
- これは出典 (NDL) の特性。アフィリエイト戦略上は**成年コミックを掲載しない**方針なので実害は無いが、false-negative 検出 (adult_mangaka_known/adult_publishers いずれにも未該当だが NDL には掲載) のリスクは残る

## 検討した追加データソース案 (2026-05-05 セッション)

### 案 A. openBD 全件 dump → 作家名 local search 【保留】

- ローカルで openBD 全 ISBN (~10M) を一括 download (~3 時間)
- 既知作家 6,751 名で絞り込んで軽量 JSON (~5-15MB) を commit
- CI 側で SQLite に import、`openbd_author_adult_ratio` signal を追加
- **判断**: ユーザ指示で保留。スケールに対してインフラ投資が重い、NDL の補完としては有用だが現在の adult 検出は十分機能している
- 詳細設計は plan file (`/root/.claude/plans/root-claude-uploads-ec200ecf-2ecf-48eb-snappy-coral.md`) の下半分に保管

### 案 B. Amazon PA-API `SearchItems` (Author 検索) 【将来本命】

- PA-API 5.0 の `SearchItems(Author=...)` で 1 作家 ~100 件 (10page × 10item) を取得
- BrowseNode `成年コミック` 含有を direct チェック → adult 判定の決定打
- ASIN 直接取得 → affiliate link 即生成可能
- カバー画像も Amazon CDN 経由で ToS 準拠
- **gate**: PA-API 承認 (180日以内 3 売上) = Phase 5 アフィリエイトサイト公開後
- **判断**: 本命。openBD よりも筋が良い (アフィリエイト target そのもの、adult 判定が direct、ASIN/画像も同時取得)

## Phase 5 までに進められる準備

完了:

- ✅ **schema 先行 migration** (2026-05-05, schema_version 4 → 5):
  - `amazon_metadata` テーブル新設 (PK = asin)。columns: `isbn13` (volumes への弱 FK), `browse_node_path` ("Books > コミック > 成年コミック" 等), `is_adult_browse_node` (0/1), `sales_rank`, `fetched_at`
  - 既存 `volumes.asin` / `volumes.cover_url` / `asins` table はそのまま (ASIN cache + locale variants で十分)
  - PA-API 承認まで空のまま。 Phase 5 開始時に migration 不要で書き込み可
  - 当初 `editions.amazon_asin` / `editions.amazon_image_url` を提案していたが、 ASIN 階層は volume レベルが正しいため amazon_metadata sidecar table に修正
- ✅ **Volume schema 拡張** (2026-05-07): `kindle_asin` (Kindle 版 ASIN) + `description` (巻ごとの説明文) を VolumeSchema に追加。 PA-API 投入時にそのまま受け入れ可
- ✅ **Manga schema 拡張** (2026-05-07): `anime_adapted` / `anime_first_year` / `alternative_titles` (en/fr/de/it/pt) / `awards` / `wikidata_qid` を MangaSchema に追加。 21 canonical + 10 newer (auto-promote) に手動 populate 済 (= 計 31 件)
- ✅ **Frontend MVP + CI auto-deploy** (2026-05-07): Next.js 15 + Tailwind の静的 export + Cloudflare Workers Assets 配信。 push trigger で 自動 build + deploy (`deploy-cloudflare.yml`)、 Android 端末完結ループ確立

未着手:

1. Associate Tag 取得 / 申請プロセス
2. 成年コミック BrowseNode ID の human 探索 (Amazon.co.jp 公開ページ経由、認証不要)
3. PA-API 5.0 SDK 選定 (公式 SDK 廃止済 → community SDK or SigV4 自前署名)
4. `computeAdultScore` への `amazon_browse_node_adult` signal 追加 (Phase 5 開始時)

## 残タスク (2026-05-07 時点)

### 短期 (家事系)
- 残り 10 件 (= title から内容判別不可な作品) の anime/alt_titles/awards 補完 — 手動 / 自動 fetcher
- 詳細ページの微調整 (= ユーザ判断待ち)

### 中期 (拡張)
- B1: 専用集計ページ — `/publishers/[key]`, `/mangaka/[name]`, `/magazines/[key]`, `/genres/[key]`, `/anime-adapted`, `/awards`
- B2: 検索 box 分離 (作品 / 漫画家 / 出版社) + autocomplete
- B3: wikidata_qid 自動取得 fetcher (series.title から Wikidata 検索 → QID)

### 長期 / Gate 待ち (Phase 5 PA-API 承認後)
- C1: 巻単位 description (Editorial Reviews を grounding に AI rewrite)
- C2: cover_url 投入 (公式 cover image)
- C3: kindle_asin 投入
- C4: adult 検出 BrowseNode 直判定 (倉科遼系の偽陽性根本解決)
- C5: Phase 5 事前準備 (BrowseNode ID 探索 / SDK 選定 / mock fetcher) — gate 待ち中でも可

### 運用
- D1: 6,751 名 全件 run (本番スケール検証)
- D2: fetch:wikipedia Layer A 改善 (検索ロジック改善で hit rate 18% → 30%+) — Phase 5 PA-API でカバーされるなら不要

---

# 2026-05-08 セッション: MADB pipeline 構築 + Tier 1 完了

## 経緯と動機

ユーザが既存 NDL pipeline (= `Wikidata QID → CSV alt_names → NDL CQL → ISBN`) の構造的限界に問題意識を持ち、 別作家混入 (false-positive) を量産する 「作家名キー駆動」 から **「ISBN list を別 source から取得 → openBD で metadata 生成」** に方向転換したいと希望。 候補として MADB (メディア芸術データベース、 文化庁 LOD) と Google Books を検討、 spec 比較の結果 MADB が圧倒的優位 (= ライセンス CC-BY 4.0 / 漫画 30 万件超 / 雑誌情報 / よみがな) と判断。

ユーザ意思 (= AskUserQuestion で確定):
1. **NDL pipeline は仕組みごと残置** (= `scripts/fetch-ndl.ts` 等は touch しない、 fallback として保持)
2. **データは MADB 由来に置換** (= 既存 NDL volume は MADB が INSERT/UPDATE で上書き)
3. **実装スコープは fetch のみ** (= promote / yaml export / workflow 統合は別プラン)

## 完成した成果物

### 新規ファイル
- `scripts/probe-madb.ts` (~570 行): MADB SPARQL endpoint への probe + schema discovery + per-author 結果 dump (read-only)
- `scripts/fetch-madb.ts` (~700 行): 本格 fetcher。 fetch-ndl の VolumeStmts pattern を踏襲、 MADB SPARQL → DB upsert
- `.github/workflows/probe-madb.yml`: probe を GH runner で実行 (= sandbox は SPARQL endpoint へ届かない)
- `.github/workflows/fetch-madb.yml`: fetch:madb 6 QID loop + fetch:wikipedia + db:report + artifact upload
- `docs/madb-probe.md`: probe 結果レポート (= 自動生成、 raw response sample 込み)

### 編集
- `package.json`: `probe:madb` / `fetch:madb` script 追加
- `scripts/db-report.ts`: `--series` で `publisher_key/magazine_key` 列 + 全体 fill rate を表示
- `MEMORY.md`: このセクション

### 不変 (= 明示的に touch しない)
- `scripts/fetch-ndl.ts` 等の既存 fetcher
- `db/schema.sql` (= sources テーブル既存、 拡張不要)
- `lib/edition.ts` (= `normalizeIsbn13` / `buildSeriesKey` 等を import)
- 既存 13 yaml (= 別プランで再生成予定)

## MADB の data model (= 5 ラウンドの SPARQL probe で判明)

### Endpoint と vocabulary
- 正規 SPARQL endpoint: `https://mediaarts-db.artmuseums.go.jp/sparql` (= **`bunka.go.jp` ではない**、 過去の試行で誤認していた)
- schema prefix: **`https://schema.org/`** (= http でなく **https**)
- class prefix: **`https://mediaarts-db.artmuseums.go.jp/data/class#`** (= `/ns/class#` ではない)
- property prefix: `https://mediaarts-db.artmuseums.go.jp/data/property#`
- HTTP: POST + form-urlencoded (= GET は URL 長制限と CDN cache で不安定)

### 主要 class (件数)
| Class | 件数 | 役割 |
|---|---|---|
| `Supplement` | 1,681,828 | 補足情報 (= 巨大だが leaf 多い) |
| `MangaBook` | 397,250 | **漫画単行本 manifestation** ← 我々の対象 |
| `AnimationTVProgram` | 197,665 | (アニメ) |
| `MangaMagazineIssue` | 179,908 | 雑誌の各号 |
| `MangaBookSeries` | 139,130 | 単行本シリーズ |
| `Agent` | 74,791 | 作家 / 出版社 |
| `MangaMagazinePublication` | 30,023 | 雑誌掲載 (= 連載作品) |
| `MangaMagazine` | 5,753 | 雑誌全体 |

### MangaBook の outgoing predicates (= fetch:madb で使う構造)
- `schema:creator` → **literal** (= Agent URI でなく `"[著]諫山創"` 等の文字列)。 役割タグ prefix 込み
- `schema:isbn` → ISBN 文字列
- `schema:publisher` → literal `"講談社　∥　コウダンシャ"` (= 漢字 ∥ カナ、 全角空白)
- `schema:datePublished` → `2020-05` 形式
- `schema:isPartOf` → **MangaBookSeries の C-id URI** (= 雑誌ではない、 確認済)
- `rdfs:label` → タイトル

### 重要発見: creator literal は役割タグ prefix
| 表記例 | 件数 (諫山創 例) |
|---|---|
| `[著]諫山創` | 48 |
| `[原作]諫山創` | 40 (= スピンオフ "進撃!巨人中学校" 等) |
| `諫山創` (bare) | 1 |

→ 完全一致 filter では bare 表記しか拾えない。 **REGEX `(^|\]|,|[ 　])NAME($|,|[ 　\]])` で末尾固定** + 役割タグ + 共著連結 (`[著]A,B`) を吸収。 `STR(?creator)` で literal 文字列を比較。

## Tier 1 実装結果 (= ユーザ「Tier 1 やって」 指示)

### Task 1: 関連書籍 / extra-vol → edition.type=other 分離
**問題**: 「金色のガッシュ!! 通常版 vols=67、 no=1..33」 (= 1巻あたり ~2 record) のような重複表示。 真因は `extractVolumeNumber` が null を返すケース (= "全巻パック" "ガイド本" "セット商品") を vol_number=1 で fallback していたこと。

**修正**: `volumeNumber === null && type === "standard"` を `type='other'` に分離。 fetch-madb.ts の `upsertVolume` 内。

**結果**: あさドラ! (8件全て other) / 金色のガッシュ!! (16件 other に分離) / Masterキートン / 進撃!巨人中学校 / 素晴らしい世界 で改善。

### Task 2: publisher literal split + master 解決
**問題**: MADB は publisher を `"講談社　∥　コウダンシャ"` (= 漢字 ∥ カナ) で発行。 `editions.imprint` にそのまま保存すると downstream で表示が汚い。

**修正**:
- `splitMadbLiteral(s)` helper で `∥` の前 (= 漢字部分) のみ抽出
- `publishers.yml` master と name 完全一致で `publisher_key` 解決
- `series.publisher_key` に `COALESCE` で UPDATE

**結果**: **publisher_key fill rate = 118/123 (96%)**。 集英社 / 小学館 / 講談社 / 白泉社 等は完全一致。 5件未解決は `クラーケンコミックス` (= 金色のガッシュ完全版 出版社) 等の master 不在 publishers。

### Task 3: magazine_key 解決 (= 5 ラウンド試行錯誤の末、 fetch:wikipedia に委譲)

**結論**: **MADB は単行本 → 雑誌 の link を構造的に保持していない**。 ユーザの UI screenshot (= 進撃の巨人 33 詳細ページ) で「関連リソース ① — 諫山創 (責任主体)」 のみが表示されることからも確認。 単行本の関連リソースは**作家のみ**で、 雑誌は無い。

**5 ラウンドの SPARQL probe 結果**:
1. ✗ `schema:isPartOf` の値は MangaBookSeries の C-id URI で、 MangaMagazine ではない
2. ✗ `schema:isPartOf+` (property path) で多 hop しても MangaMagazine に届かない
3. ✗ MangaBookSeries の outgoing entity link は **Agent (= creator) のみ**、 MangaMagazine 直接 link 0 件
4. ✗ MangaMagazinePublication は leaf entity (= 他 entity への link 無し)
5. ✗ (name, creator) で BookSeries ↔ MagazinePublication を bridge する案も exact match 失敗 (= 進撃の巨人 で確認)

→ 173k 件の `incoming schema:isPartOf to MangaMagazine` はすべて **MangaMagazineIssue から**。 単行本サブグラフから雑誌サブグラフへの渡る predicate が**存在しない**。

**最終決定** (= ユーザ承認、 推奨案):
- MADB から magazine 取得は諦める (= graph 構造的に不可能と判断)
- 既存の `fetch:wikipedia` で magazine_key を補完 (= NDL pipeline で実証済)
- データ責務分担:
  | source | 担当 |
  |---|---|
  | **MADB** | ISBN / publisher_key / volume_number / release_date / edition.type |
  | **Wikipedia** | magazine_key / title_kana / genres / synopsis / demographic |

**コード変更**: `scripts/fetch-madb.ts` から magazine 関連 code を全削除 (= `magazines.yml` 読込、 `updateSeriesMagazineKey`、 `magazineKey` resolve 経路、 `discoverIsPartOfChain` Phase 0+ など)。 `.github/workflows/fetch-madb.yml` に `fetch:wikipedia` step 追加 + 探索用 debug step を全削除。 -255 / +32 lines で大幅 simple 化。

## Workflow 構成 (= 一気通貫)

```
db:init
  → import:masters (= publishers.yml + magazines.yml)
  → import:mangaka (= 6,751 mangaka CSV)
  → fetch:madb (= 6 QID loop)            ← MADB 担当
  → fetch:wikipedia                      ← Wikipedia 担当
  → db:report (= 結果検証)
  → artifact (= db.sqlite + raw dumps)
```

## 6 作家 probe / fetch の最新結果 (= 7-8 回目 GH run)

| 作家 | QID (= CSV 真値) | hits | unique ISBN | 主要 series |
|---|---|---|---|---|
| 諫山創 | Q3782468 | 89 | 89 | 進撃の巨人 (54件) + 派生 6 series |
| 高屋奈月 | Q241885 | 79 | 76 | フルーツバスケット (35件) + Another (4) + 他 |
| 浦沢直樹 | Q348436 | **328** | 265 | YAWARA! (65) / Masterキートン (25) / 20世紀少年 (23) / Pluto (15) / Billy Bat (20) 等 |
| 浅野いにお | Q600217 | 63 | 63 | おやすみプンプン (22) / DDD (19) / 他 |
| 吾峠呼世晴 | Q24865213 | 33 | 33 | 鬼滅の刃 (25) + キメツ学園! (6) |
| 雷句誠 | Q972529 | 131 | 121 | 金色のガッシュ!! (83件、 通常+完全+その他) / どうぶつの国 (14) / 等 |

**DB 投入結果**:
- series: 123
- editions: 131 (= Task 1 の other 分離で +7)
- volumes: 689
- sources `madb`: 689 行
- publisher_key fill: **118/123 (96%)**
- magazine_key fill: **26/123 (21%)** ← Wikipedia 補完で 0 → 26 (= 2026-05-08 wiki 実走で達成、 layer C 解決率 100%)
- publisher_key fill: **119/123 (97%)** ← MADB 118 + Wiki 補完で +1
- title_kana fill (Wiki 由来): 18/123 / synopsis: 37/123 / genres: 20/123
- Layer A 記事発見率: **31% (38/123)** ← MADB の series 粒度が細かすぎ (= Monster が 10 series、 Happy! が 16 series 等に分割) で Wikipedia 検索 hit 率が低い。 真の改善は Tier 2 #1 (重版集約) / #4 (yaml 再生成) 必要
- **2026-05-08 baseTitle 強化後**: series **123 → 83 (-33%)**, Wikipedia hit rate **31% → 46% (+15pt)**, magazine_key fill **21% → 31%**。 Monster 10 series → 1、 Happy! 16 → 1、 20世紀少年 12 → 1 series に集約。 「20世紀少年 通常版 22 巻 + 完全版 11 巻」 が同 series 内 2 edition (= standard + other) に分離成功 (= ただし完全版 entries が `kanzenban` でなく `other` になっている件は要追加調査、 MADB title に「完全版」 keyword が含まれていない可能性)

## 重要な hardcode 修正 履歴

私 (Claude) が初期に hardcode した QID が CSV と全部不一致で、 fetch-madb で mangaka resolve 失敗 → 0 件投入した bug があった。 修正済 commit `7cb1815`:

| 作家 | 旧 (誤、 私の Wikidata 知識違い) | 新 (CSV 真値) |
|---|---|---|
| 諫山創 | Q11331084 | **Q3782468** |
| 高屋奈月 | Q231007 | **Q241885** |
| 浦沢直樹 | Q310385 | **Q348436** |
| 浅野いにお | Q1145902 | **Q600217** |
| 吾峠呼世晴 | Q56022442 | **Q24865213** |
| 雷句誠 | Q1366247 | **Q972529** |

probe-madb は QID 使わず name literal で SPARQL を叩いていたので結果自体は正しかったが、 表示 QID は誤値だった。

## SQLite NOT NULL 違反 修正 履歴

`fetch-madb` 初版で series=N / editions=0 / volumes=0 になった bug。 原因: スキーマの NOT NULL 制約見落とし。 修正済 commit `ae3e1d8`:

- `editions.label NOT NULL` → `EDITION_LABELS[type]` (= "通常版" / "完全版" 等) を渡す
- `volumes.number NOT NULL` → `volumeNumber ?? 1` + null 時は `is_extra=1` flag

`upsertVolume` は try/catch で各 record 独立処理するため、 series insert 成功直後の edition insert で SQLite NOT NULL 違反 → catch で skip → 次 record、 という流れで series だけ commit されていた。

## 未解決の課題 (= Tier 2 候補)

### 1. 重版 ISBN の集約 (= 同 vol_number で複数 ISBN)
**症状**: 進撃の巨人 standard vols=54 だが no=1..34 (= 34 巻なのに 54 record、 vol1×2 / vol8×2 等)。 鬼滅の刃 vols=25 (= vol20×2, vol21×2)。 フルーツバスケット vol1..vol8 各 ×2。

**原因**: MADB は同一巻の複数 ISBN (= 通常版 + 限定版 + コンビニコミック + 重版) を独立 manifestation として保持している。 fetcher は data fidelity を保つため raw に投入。

**対処**:
- A. fetch 段で `(series, type, vol_number)` 単位で 1 ISBN に正規化 (= 最古発行を採用、 他は別 edition.type='other' か skip)
- B. promote 段で正規化 (= yaml 出力時に重複排除)
- C. 重版を edition.type='renewal' / 'other' に細分化

ユーザと方針相談すべき。

### 2. fetch:wikipedia の実走確認
fetch-madb workflow に追加した `fetch:wikipedia` step がまだ実行確認できていない。 期待: magazine_key fill rate が数十/123 になる。 次 run で要確認。

### 3. promote:bulk の MADB 対応
現状 promote:bulk は NDL fetch を前提にしている可能性。 MADB データから yaml 生成できるよう調整が必要。 別プラン。

### 4. 既存 13 yaml の MADB 再生成
現状の `data/manga/*.yml` (= 13 件、 NDL 由来) を一旦削除 → MADB run で再生成。 ユーザの「データ置換」 意思の最終形。

### 5. bulk-promote-test workflow への統合
現状 fetch-madb は standalone workflow。 bulk-promote-test に組み込む案は「Out of scope」 と plan に明記、 別プラン。

### 6. publisher master 不在 publishers の補完
118/123 = 5件未解決。 例: クラーケンコミックス (= 金色のガッシュ完全版)。 `data/publishers.yml` master を拡張するか、 fuzzy match を追加するか。

### 7. MADB 未収録作家の fallback
ユーザ意思 1 (= NDL 仕組みは残置) は、 MADB hit=0 のとき NDL fetch を起動する fallback ロジックを将来書く可能性を残している。

## 関連 commit (= 開発履歴の trail)

```
8dccac4  feat(fetch-madb): Phase 0+ schema discovery for schema:isPartOf chain
fcadf68  ci(fetch-madb): direct SPARQL probe for MangaBookSeries → MangaMagazine link
ff33762  ci(fetch-madb): pivot via MangaMagazinePublication for magazine link
a0dc91f  ci(fetch-madb): probe MangaMagazinePublication chain via incoming predicates
3eeee91  feat(fetch-madb): close Tier 1 — magazine_key delegated to fetch:wikipedia
d769cb6  feat(db-report): show publisher_key/magazine_key in --series view
c5889c1  feat(fetch-madb): Tier 1 — extra-vol split, publisher/magazine resolve
ae3e1d8  fix(fetch-madb): satisfy NOT NULL constraints for editions.label / volumes.number
7cb1815  fix(madb): correct hardcoded QIDs to match data/seed/mangaka.csv
18642a9  feat(fetch-madb): MADB SPARQL fetcher (NDL pipeline と並走)
9980ee6  fix(probe-madb): treat schema:creator as literal (not URI ref)
033d5bb  fix(probe-madb): match creator with role-tag prefix via REGEX
2e5296f  fix(probe-madb): apply real vocabulary discovered via Phase 0+
6efda01  feat(probe-madb): add Phase 0+ schema discovery to find real vocabulary
df2a759  fix(probe-madb): use correct endpoint artmuseums.go.jp + MangaBook vocabulary
fa002bf  ci(probe-madb): add workflow_dispatch to run MADB probe on GH runner
a475e1e  probe(madb): narrow scope to MADB only, drop Google Books
c879e72  probe(isbn-sources): add Google Books + MADB comparison probe
```

## プロセス上の反省 (= 今後のセッションで注意)

ユーザに **「相談してほしかった」** と指摘された。 magazine_key の探索で 5 ラウンドの GH workflow run を消費した直後、 ユーザが UI screenshot (= 進撃の巨人 33 の関連リソース欄) を提示し、 「関連リソース 1件 = 作家のみ」 = 単行本に雑誌 link なしが UI 上から自明だった。

**次セッションの行動指針**:
1. **API を叩く前に UI / 公式ドキュメントで data モデルを先に確認** する。 文化庁 LOD はドキュメント整備されているはず
2. **仮説が 2 回連続外れたら iterate でなく相談に切り替える**。 「これは MADB の構造的制限と思われます。 UI で確認できますか?」 のような短い質問で済む話だった
3. **GH workflow run を消費する前に**、 ユーザに UI / docs 確認を依頼する選択肢を提示する
4. ユーザは Android スマホで UI を確認可能。 こちらが見えない情報 (= UI / 内部 data 構造) は積極的に依頼してよい

## 次セッションでの推奨スタートアクション

1. このファイル (`MEMORY.md`) を Read
2. `git status` と `git log -10 --oneline` で進捗を把握
3. ユーザに「Tier 2 (= 重版 ISBN 集約 / promote 統合 / yaml 再生成 / bulk-promote-test 統合) のどれから進めますか?」 と聞く
4. もしくは fetch:wikipedia 実走確認の結果次第では magazine_key fill rate の確認 + 不足分の対処
5. ユーザの方針が定まらないなら、 「未解決の課題」 セクションから tractable な 1 件を提案

## ブランチ

- 開発ブランチ: `claude/manga-database-affiliate-3x0ms`
- すべての変更はこのブランチ上で commit/push
- main へ merge していない (= ユーザの判断待ち)

---

# 2026-05-08 (午後): MADB SPARQL → CSV → JSON-LD 路線に最終確定

## 最終形 (= JSON-LD)

公式 GitHub `mediaarts-db/dataset` の release asset
(= 例 tag `1.2.15`、 `metadata101_json.zip` 47.5MB / 展開 627MB) を直接
streaming 読み込み、 397k records を 1 パスで処理する。

成果物:
- `lib/madb-jsonld.ts` (= 30 unit tests 緑)
- `scripts/fetch-madb.ts` (= stream-json + stream-chain で streaming JSON 処理)
- `.github/workflows/fetch-madb.yml` (= release_tag input、 GitHub API で
  latest 自動解決、 zip download → unzip → import)

ローカル実 run (= 6,751 mangaka 全員 vs cm101 全 397k records):
- 所要時間: **1m35s** (= ≈4,184 records/sec)
- adult filter: rating 8,155 (1次) + imprint 4,928 (3次追加 catch) = 13,083 件 skip
- 投入: 6,650 series / 6,729 editions / 10,615 volumes / 6,650 author 紐付け
- top series: ゴルゴ13 70巻、 ドラえもん 69巻、 名探偵コナン 38巻、 ONE PIECE 31巻
- edition type 内訳: standard 3376 / other 3346 / kanzenban 5 / aizoban 2

## 経緯 (= 1 日で 3 回方針転換)

### 1. SPARQL 路線 (午前) — 廃案

probe + 5 round の schema discovery で完全版判定 (= cm106 isPartOf 経由) 不可、
magazine link は MADB 構造上 SPARQL でも取れない (= MangaBook → MangaMagazine
関係が standalone records で表現)。

### 2. CSV 路線 (午後前半) — 一時実装後に転換

ユーザがアップした `cm104_*.csv` (10000 件、 cm101 差分) を発見。
公式 `レーティング` column で 1 行 filter に成功。 lib/madb-csv.ts +
scripts/fetch-madb.ts (CSV) を実装、 cm104 でローカル検証 OK (commit `e9c9d86`)。

しかし公式 GitHub release は CSV 提供なし (= JSON-LD / TTL のみ) と判明。
portal 由来 CSV は dynamic URL でめんどう。

### 3. JSON-LD 路線 (午後後半) — 最終確定

公式 GitHub release が JSON-LD で **stable URL + 自動化容易** と判定して切換。
JSON-LD 内部構造で重要発見:
- `schema:contentRating` = "成年コミック" → CSV と同じ adult signal
- `schema:alternativeHeadline` = サブタイトル (= 「完全版」 等が入る) →
  classifyEdition の最優先入力
- 共著は `schema:creator` array に複数 string 要素を flat に並べる
- 単一 JSON 内 `@graph` array に全 record → stream-json 必須

## ユーザ意思決定の trail (= AskUserQuestion 3 回)

1. CSV/SPARQL データソース → "C: cm101 全量 CSV" → 後に JSON-LD に再転換
2. 成年コミック扱い → "完全除外、 ぬけがあると思われる" → 4 層 filter 設計
3. JSON-LD vs TTL → "JSON-LD" → 最終確定

## 4 層 adult filter の効き (= 397k records 実走実測)

| 層 | 件数 | 比率 |
|---|---|---|
| 1. schema:contentRating | 8,155 | 2.05% |
| 2. schema:description text match | 0 | (1 次で全 catch) |
| 3. schema:brand → adult_imprints | 4,928 | 1.24% |
| 4. schema:publisher → adult_publishers | 0 | (seed が空) |

3 次が 4,928 件追加 catch していて、 これは rating 空欄でも adult imprint 由来の
record。 ユーザ懸念 「ぬけがあると思われる」 が **実証** された (= 公式 rating
column だけでは漏れる)。

ただし 3 次は false-positive も含む (= ヴァルキリー / GOT は本物 adult、 マン
サン / SP は mainstream の混在)。 既存 Phase 0-5 計画 (adult_imprints seed
quality 改善) で対処予定。

## アーキテクチャ転換: 既存プランへの影響

| プラン | 扱い |
|---|---|
| 「MADB 本格 fetcher (SPARQL)」 | **廃案**。 JSON-LD 路線で全面書き直し済 |
| 「baseTitle 強化プラン」 | **継続有効**。 lib/edition.ts は JSON-LD 路線でも必要 |
| 「完全版判定 + chapter 集約」 | **大幅縮小**。 schema:alternativeHeadline が直接判定材料 |
| 「Tier 1B DENY_LIST + adult_imprints」 | **継続有効、 役割変更**。 4 層 filter の 3 次 catch を担う |
| 「fetch:wikipedia hit-rate 解明」 | **継続有効**。 magazine_key は JSON-LD でも取れない |

## 次セッションでの推奨アクション

1. **GH workflow 実 run** (= release tag を空で latest 自動解決させる)。
   ローカル 1m35s なので CI でも 数分。 6,751 規模 coverage 計測。
2. 既存 50 mangaka batch との比較 (= NDL のみ vs MADB JSON-LD のみ)
3. adult_imprints seed quality 改善 (= マンサン / SP コミックス false-positive 除外)
4. その後 promote-bulk 統合 → yaml 再生成

---

# (旧記録) 2026-05-08 午後: MADB SPARQL → CSV 路線に転換

## 経緯

ユーザが MADB 公式 download 機能由来の `cm104_*.csv` (= 10000 件、 cm101 全量
の差分 export) をアップロード。 中身を分析して以下が判明:

1. **`レーティング` column の存在**: 成年コミック判定が **1 列の equality check**
   で完結。 SPARQL で組もうとしていた publisher/imprint ベース判定 (= Phase 0-5
   既設計) より圧倒的にクリーン。 cm104 では 216 件 (2.16%) が rating=成年コミック。
2. **「版表示」「巻」 column が独立化**: `完全版` / `特装版` / 巻番号が CSV では
   structured で取得可能。 SPARQL で必要だった schema discovery / chapter 集約
   ロジックが不要になる。
3. **rate limit 一切なし**: 70MB CSV を 1 パス読むだけで 397k record 全件処理可能。

ユーザ意思決定 (= AskUserQuestion 2 回):
- **データソース**: cm101 全量 CSV を毎回 fetch (= SPARQL 廃止)
- **adult 扱い**: import 時に完全除外、 「ぬけ」 catch のため二重 filter

## 完成した成果物

1. **`lib/madb-csv.ts`** (新規、 ≈210 行) — CSV parser + 4 層 adult filter +
   row 変換ユーティリティ
2. **`lib/madb-csv.test.ts`** (新規、 26 tests) — parser / adult filter /
   author 分割 / volume 数値化 / BOM strip 全 unit test 緑
3. **`scripts/fetch-madb.ts`** (全面書き換え、 SPARQL → CSV) — 1 パス CSV 読み +
   作者 1:N index 紐付け + 既存 upsertVolume パターン流用
4. **`.github/workflows/fetch-madb.yml`** (改修) — `csv_url` input 受け付け、
   curl 取得 → `--csv-path` 渡し、 SPARQL probe step 撤去

## ローカル検証結果 (= cm104 で 100 mangaka sample)

```
[csv] read 10000 rows, parsed=10000, matched=24, queued=24
  total rows           : 10000
  parsed rows          : 10000
  parse errors         : 0
  skipped (rating)     : 216    ← 1 次 filter (= MADB 公式 rating)
  skipped (summary)    : 0      ← 2 次 (= rating 漏れ catch、 cm104 では発火なし)
  skipped (imprint)    : 48     ← 3 次 (= adult_imprints DB 照合、 ヴァルキリー等 catch)
  skipped (publisher)  : 0      ← 4 次 (= adult_publishers DB 照合)
  matched rows         : 24
  upserted volumes     : 24
    inserted           : 24
```

→ 1 次 (= レーティング column) で 216 件全件 catch、 3 次 (= imprint 照合) で
さらに 48 件追加 catch (= レーティング空欄でも adult imprint 由来の record)。
ユーザ懸念 「ぬけがあると思われる」 への保険として機能している。

検証で確認した投入データの精度:
- publisher_key 解決: shonen-gahosha / kadokawa / mag-garden 等 全て publishers.yml と整合
- imprint 値: HARTA COMIX / ACTION COMICS / ヤングジャンプコミックス・ウルトラ 等正確
- volume 番号: CSV 「巻」 column 直接採用で 7 / 14 / 6 / 9 / 11 等 正解
- edition type: 巻番号取れた record は standard、 取れない 「けんかめし」 は other
- author 紐付け: ONE → ワンパンマン + バーサス (= 1:N 紐付け正常)

## アーキテクチャ転換: 既存プランへの影響

| プラン | 扱い |
|---|---|
| 「MADB 本格 fetcher (SPARQL)」 | **廃案**。 CSV 路線で fetch-madb.ts 書き直し済 |
| 「baseTitle 強化プラン」 | **継続有効**。 lib/edition.ts の baseTitle rule は CSV 路線でも必要 |
| 「完全版判定 + chapter 集約」 | **大幅縮小**。 CSV の「版表示」 column が直接判定材料 |
| 「Tier 1B DENY_LIST + adult_imprints」 | **継続有効、 役割変更**。 CSV `レーティング` 漏れ catch 用 secondary filter |
| 「fetch:wikipedia hit-rate 解明」 | **継続有効**。 magazine_key は CSV / JSON-LD でも取れない |

## 次セッションでの推奨アクション

1. ユーザが **cm101.csv 全量 をアップロード** (= 公式 portal 由来) → 397k 件
   フル import で 6,751 mangaka 全員 coverage 計測
2. 既存 50 mangaka batch との比較 (= NDL のみ vs MADB のみ)
3. workflow GH run で `csv_url` 経由動作確認 (= 公式 download URL 確定後)
4. adult_imprints seed quality 改善 (= マンサンコミックス / SP コミックス 等の
   false-positive 除外)。 既存 Phase 0-5 計画範疇

---

# 2026-05-08 (夜): 3-state model 導入 (live/excluded/archive) + 管理 UI

## 経緯と動機

ユーザの要件:

> 「除外したものがちゃんと残っていつでも復帰できる構造」
> 「管理者だけ閲覧可能で、 確実に削除な状態」
> 「3 つの DB に分けたい (= 公開・除外・全履歴)」

既存の adult filter 設計 (= adult signal で当たったら fetch 時に DROP、 後で取り戻せない)
を見直し、 import の全 record を archive に保持し、 公開する live と review 中の
excluded と完全削除済み deleted を区別する **3-state model** に転換した。

ユーザの mental model 「3 つの DB」 は、 操作の整合性 (= cross-state reinstate を
1 transaction で扱える) を考えて 1 file 内 3 テーブルで実装。

## 設計

### Schema v7 (= 3 新テーブル + 1 INDEX 群)

```
series_archive   ← 全 import 履歴の source-of-truth。 削除しない (UPDATE のみ)。
                   current_state ∈ {live, excluded, deleted} で意味を付与する。
                   live=series テーブルにあり公開中、 excluded=series_excluded
                   にあり管理者 review 中、 deleted=どちらにも無い (= archive
                   にのみ残存、 監査 / 復活専用)。

series_excluded  ← 管理者 review queue (= 「グレーゾーン」)。 archive_id PK +
                   reason / signals_json / excluded_at / excluded_by。
                   reason は 'adult_rating' / 'adult_imprint' /
                   'adult_publisher' / 'adult_description' / 'manual_admin' 等。

admin_audit      ← reinstate / permanent_delete / manual_exclude の監査ログ。
                   action / target_id / performed_by / reason / metadata_json。
```

(`series` / `editions` / `volumes` / `series_authors` 等の既存テーブルは
 そのまま **live state の row** を保持する役割になる。 schema 変更なし。)

### 状態遷移

```
import 時 (scripts/fetch-madb.ts):
  archive 無し         → archive.live (clean) または
                         archive.excluded + series_excluded (adult signal)
  archive.live         → live のまま、 adult signal を 無視 (= sticky reinstate)
  archive.excluded     → 引き続き excluded
  archive.deleted      → 全て no-op (= 完全削除済み、 import が来ても復活しない)

admin 操作 (lib/admin-state.ts):
  excluded → live      reinstate (= series stub 行を archive snapshot から作成、
                       series_excluded から DELETE、 archive.current_state=live、
                       admin_audit に reinstate 記録)
  excluded → deleted   permanent_delete (= series_excluded から DELETE、
                       series テーブルにあれば DELETE [cascade で editions/
                       volumes も]、 archive.current_state=deleted、 archive 行
                       自体は残す。 admin_audit に permanent_delete 記録)
  live     → excluded  manual_exclude (= series テーブルから DELETE、
                       series_excluded に upsert、 archive.current_state=excluded、
                       admin_audit に manual_exclude 記録)
```

reinstate 後は **`npm run fetch:madb` 再実行で巻情報が再投入される**
(= archive.current_state='live' が sticky に効き adult signal を無視するため)。

### Sticky semantics の意義

- 「admin が誤検出を救った series」 が 次回 import で 再度 自動 excluded に飛ばされない
- 「admin が確実に削除した series」 が 再 import で勝手に復活しない
- 全ての操作が admin_audit に残るため、 後追いで「誰が、 いつ、 何を、 なぜ」 が分かる

## 完成した成果物

### 新規ファイル
- `lib/admin-state.ts` (~330 行): 純 library。 listExcluded / countExcluded /
  excludedReasonCounts / reinstate / permanentDelete / manualExcludeSeries /
  listAudit。 全操作が transaction + admin_audit logging
- `scripts/admin-state.ts` (~180 行): CLI。
  ```
  npm run admin:state list-excluded [--reason X] [--limit N]
  npm run admin:state counts
  npm run admin:state reinstate --archive-id N --by USER [--reason ...]
  npm run admin:state delete    --archive-id N --by USER [--reason ...]
  npm run admin:state exclude-series --series-id N --by USER [--reason ...]
  npm run admin:state audit
  ```
- `scripts/admin-server.ts` (~460 行): standalone local 管理 UI server。
  - zero-deps node:http、 Basic Auth (= ADMIN_USER / ADMIN_PASS env、 未設定なら起動拒否)
  - ADMIN_HOST 既定 = `127.0.0.1` (= LAN 非公開)、 ADMIN_PORT 既定 = 8787
  - server-rendered HTML、 minimal CSS、 noindex meta
  - GET /admin/excluded (= reason filter / pagination / 復帰・削除ボタン)
  - GET /admin/audit (= 監査ログ + metadata pretty print)
  - POST /admin/api/reinstate / delete / exclude-series → lib/admin-state.ts へ委譲
- `scripts/backfill-archive.ts`: 既存 6650 series → series_archive 一回限り migration (= schema v7 移行)

### 編集
- `db/schema.sql`: schema_version 6 → 7、 3 新テーブル + 7 INDEX 追加。
  `INSERT OR IGNORE` だけでは既存 DB の version が上がらないので
  `UPDATE meta SET value='7'` も追加 (= migration 兼用)
- `scripts/_db.ts`: `applySchemaIfNeeded` を **「mangaka テーブルが無ければ流す」**
  から **「常に exec」** に変更。 schema.sql は全 `CREATE TABLE IF NOT EXISTS` /
  `CREATE INDEX IF NOT EXISTS` / `INSERT OR IGNORE` で書かれていて idempotent
  なので毎回 exec しても安全 (= 既存 DB に新テーブル / INDEX だけが追加される)。
  将来 ALTER TABLE 等の非 idempotent migration が必要になったら schema_version
  分岐に切り替える方針
- `scripts/fetch-madb.ts`: 大幅改修。
  - adult signal を **早期 skip しない**。 全 matched record を queued に積む
  - 各 record に `seriesKey` + `adultSig` を付与
  - Transaction 内 2 pass:
    - Pass A: seriesKey 単位に集約 (= adult signal set / year span / publisher)
      → series_archive を upsert + state 判定 (= live / excluded / deleted skip)
      → excluded なら series_excluded を upsert (= signals_json + reason)
    - Pass B: queued の record 1 つずつ upsertVolume (既存路線)。
      ただし Pass A で goLive=false 判定された seriesKey の record は skip
  - Stats を改編 (= `excludedSeries` / `archivedSeriesNew` / `liveDespiteSignal`
    / `skippedDeleted` 等の新カウンタを log 出力)
- `data/seeds/adult-imprints.yml`: 17 imprint を `imprints[]` から
  `false_positives[]` セクションへ移動 (= 252 → 235 投入対象)
- `lib/adult-imprints.ts`: `AdultFalsePositiveSchema` 追加 (= imprint /
  publisher / fp_total / total_hits / fp_rate / note)、 `AdultImprintsFileSchema`
  に `false_positives` を optional で追加
- `scripts/seed-adult-imprints.ts`: false_positives count を log 出力 (= 投入は
  しないが視認性を上げる)
- `scripts/fetch-wikipedia.ts` / `scripts/fetch-ndl.ts`: filename sanitizer を
  `encodeURIComponent → replace(/%/g, "_")` から
  `encodeURIComponent → replace(/[^A-Za-z0-9._-]/g, "_")` に強化。
  encodeURIComponent は `* ' ( ) ! ~` を escape しないので、
  タイトル末尾 `*` (= 「不安の種*」) が filename に残って
  actions/upload-artifact@v4 (= 不正文字 `* " : < > | ? \r \n` を含むパスを
  reject) で失敗する事象を修正 (= GH Actions Fetch MADB workflow が 2h50m
  完走後に Upload artifact step で停止していた)
- `package.json`: `db:backfill-archive` / `admin:state` / `admin:server`
  scripts 追加

## adult_imprints false-positive 整理 (= 17 件)

`scripts/probe-adult-imprints.ts` (= MADB JSON-LD vs schema:contentRating で
TP/FP 集計) を実走し、 FP rate >=50% の 17 entry を identify:

| imprint | publisher | total | FP rate | サンプル mainstream |
|---|---|---|---|---|
| SPコミックス | リイド社 | 2212 | 100% | ゴルゴ13 / 浅見光彦 系 |
| マンサンコミックス | 実業之日本社 | 1526 | 100% | 浅見光彦トラベルミステリー |
| ヴァルキリーコミックス | キルタイムコミュニケーション | 409 | 100% | 異世界喰滅のサメ 等 |
| コアコミックス | コアマガジン | 181 | 93.9% | 過半 mainstream |
| ネオコミックス | 辰巳出版 | 12 | 91.7% | 極楽レディース 等 |
| OKS COMIX | オークス | 74 | 83.8% | BLACK GENERATION 等 |
| ワールドコミックス | 久保書店 | 92 | 76.1% | バーサスアース 等 |
| 別冊エースファイブコミックス | 松文館 | 248 | 57.7% | きまぐれギャルビーチ 等 |
| TECHGIAN STYLE | KADOKAWA | 15 | 100% | フォトカノHappy Album |
| ダイナコミックス | 松文館 | 4 | 100% | (small sample) |
| マイウェイコミックス | メディアックス | 2 | 100% | (small sample) |
| ダイトコミックス | 大都社/少年画報社 | 2 | 100% | 湘南グラフィティ |
| ホットミルクコミックス | コアマガジン | 1 | 100% | (sample 1) |
| コミック文庫 | フランス書院 | 1 | 100% | (sample 1) |
| DOコミックス | ヒット出版社 | 1 | 100% | (sample 1) |
| サンワコミックス | 三和出版 | 2 | 50% | (small sample, ambiguous) |
| TENMA COMICS EX | 茜新社 | 2 | 50% | (small sample, ambiguous) |

`adult_imprints` テーブル: 252 → **235 行** (= refresh 後)。
これにより mainstream 漫画 (= ゴルゴ13・浅見光彦・異世界系 等) が adult_imprint
シグナルで誤検出される問題が大幅に解消。

## 検証

- `npx tsc --noEmit` 全 clean
- `npm test` (vitest) **154 / 154 passed**
- admin-state CLI smoke test:
  live → excluded → reinstate → permanent_delete → reinstate 全遷移成功、
  audit log に 4 操作全て記録される
- admin-server smoke test:
  401 (no auth) / 200 (with auth) / 303 (POST → redirect) 全期待通り、
  /admin/excluded と /admin/audit 両 page render 成功

## 起動方法 (= 運用 cheat sheet)

```sh
# 既存 DB を schema v7 へ migrate
npm run db:init                 # 新テーブル/INDEX 追加 (= 既存 series 6650 件 保持)
npm run db:backfill-archive     # series → series_archive 複製 (= 一回限り、 冪等)

# 管理 UI 起動
ADMIN_USER=ops ADMIN_PASS=secret npm run admin:server
# → http://localhost:8787/admin/excluded

# CLI 操作
npm run admin:state list-excluded
npm run admin:state counts
npm run admin:state reinstate --archive-id 123 --by ops --reason "誤検出"
npm run admin:state delete --archive-id 123 --by ops --reason "確実に成人向け"
npm run admin:state audit
```

## 注意事項

- **admin 操作後は静的サイトを再 build** (`npm run build`) して `out/` を更新する
  必要あり。 admin-server は本番 site cache の invalidation までは行わない
- reinstate は series stub 行のみ作成 (= editions / volumes は空)。
  巻情報を埋めるには `npm run fetch:madb -- --jsonld-path .cache/madb/metadata101.json --all`
  を再実行する (= sticky reinstate により adult signal が無視され自然に埋まる)
- `next.config.ts` の `output: "export"` のため admin UI は Next.js に組み込め
  ない (= server runtime 無し)。 admin は **localhost-only の standalone server**
  として運用、 公開デプロイには含めない
- ADMIN_USER / ADMIN_PASS が未設定なら admin-server は起動拒否 (= 事故防止)。
  ADMIN_HOST も 既定 `127.0.0.1` で LAN 非公開

## 関連 commit

```
aa3d921  feat(schema): add 3-state model (live / excluded / archive) tables
f6b6329  feat(3-state): wire fetch-madb to archive/excluded + admin lib & CLI
df26df4  feat(admin): standalone local admin server with Basic Auth + UI
f0f953d  chore(adult-imprints): move 17 high-FP-rate seeds to false_positives
c734395  fix(fetch): sanitize cached filenames so upload-artifact accepts them
```

## 次セッションでの推奨アクション

1. **localhost で admin-server を起動**して /admin/excluded を実際に開く
   (= ユーザ自身が UI を触ってフィードバックを得る)。 ローカル DB に excluded
   行を入れるには `fetch:madb --all` を再実行するか、 `admin:state exclude-series`
   で既存 series を手動で excluded に飛ばす
2. fetch:madb の本番 GH run (= filename sanitizer fix が効いて完走するか)
3. ユーザのフィードバックを受けて UI 微調整 (= フィルタ追加 / 一括操作 /
   エクスポート 等)
4. 「未解決の課題」 セクション #1 (= 重版 ISBN 集約) や #4 (= 既存 13 yaml の
   MADB 再生成) は引き続き別プランで持ち越し

---

# 2026-05-10: 種3 (series-supplement.yml) AI 直筆 fill 進捗 + 月次蒸留 protocol

## 種の整理 (= 用語確定)

- **種1 (seed1)**: MADB raw 源 (= cm101.csv / metadata101.json) + `data/seed/mangaka.csv` (= 6,751 mangaka master)
- **種2 (seed2)**: 派生 SQLite DB (= `.cache/db.sqlite`、 series=70,202 / editions=71,480 / volumes=222,315 / mangaka=6,751)
- **種3 (seed3)**: `data/seeds/series-supplement.yml` (= 70,202 entries、 schema_version 1、 generator `claude-opus-4-7-direct-fill`)

種3 は **AI (= Opus 4.7) 直筆 fill** で per-series に以下を埋める supplement layer:
- `magazine` (= 連載誌 string、 magazines.yml に master 不在の値も自由記述)
- `demographic` (= shounen / shoujo / seinen / josei / kodomo / other)
- `genres` (= 25 master keys から複数選択)
- `synopsis` (= 1-3 文の要約)
- `status` (= ongoing / completed / hiatus)
- `anime_adapted` (= bool)

batch JSON 形式: `{"qid|baseTitle": {magazine, demographic, genres, synopsis, status, anime_adapted}}`、
`scripts/_apply-fills.ts` で apply、 各 batch 後 `applied=N missing=0` 確認。

## fill 進捗 (= ✅ 100% 完了、 70,202 / 70,202、 2026-05-13 達成)

種3 fill の **全 70,202 件が 2026-05-13 に完了** (= session 1-37、 batch 1-705)。
作り方 / per-batch protocol / PUA 文字特殊処理 等は本ファイル末尾 「種3 fill 作り方 (= 再利用 guide)」 セクションを参照。 月次蒸留 / 新規シリーズ追加時はそれを踏襲する。

## 月次蒸留 protocol (= 2026-05-10 登録、 commit `4402d3a`)

ユーザが **「月次蒸留して」** (= 完全一致トリガー) と発話したら、 私 (= Claude) が以下を厳密に実行する。 永続化先: `CLAUDE.md` (= 毎 session 自動読み込み、 `/clear` 後も保持)。

### 大原則 (= 絶対遵守)
**種1 / 種2 / 種3 は壊さない**。 差分追加 = **純粋追加 only**、 既存への上書き / 削除 / 編集は禁止。
検出時は即 abort + ユーザ通知。

### Phase 0: 前提確認 (= 1 つでも欠ければ即 abort + ユーザ通知)
- `.cache/madb-last-release.txt` (= 前回取込 MADB release tag)
- `.cache/db.sqlite` (= 種2)
- `data/seeds/series-supplement.yml` (= 種3)
- `data/seed/mangaka.csv` (= 種1)
- `scripts/_diff-madb.ts` / `_diff-series.ts` / `_select-supplement-diff.ts` (= 未実装)
- `git status` clean

### Phase 1: 差分 report → Go サイン待ち
種1/2/3 の差分件数 + AI fill 予想 batch 数 + 削除予測 0 を表示、 ユーザ Go サイン受領まで Phase 2 に進まない。

### Phase 2: Go サイン後の実行
種1 取込 → 種2 incremental fetch → 種3 diff 元生成 → AI fill batch loop (= 100 entry/batch、 JST 報告、 commit + push) → 最終 summary。

### 5 層保護策
1. 取込前 `.cache/db.sqlite` を `.cache/db.sqlite.bak-YYYYMMDD-HHMMSS` に backup
2. 種1/2/3 各取込は単独 commit で分離 (= revert 容易)
3. 各 batch 後 `applied=N, missing=0, overwrites=0` 強制 log
4. tsc / vitest が以前緑なのに赤転落で abort
5. 想定外 delete / overwrite 検出で abort

### 本番 DB 生成は対象外
yaml export / promote pipeline は **月次蒸留の範囲外**。 改善余地が残っているので、 時期が来たらユーザから別途相談 → 設計確定 → CLAUDE.md に追記、 の流れで対応。

## 月次蒸留が動くために必要な未実装 (= 次セッション以降の宿題)

- `scripts/_diff-madb.ts` (= 種1 差分抽出、 前回 release との比較)
- `scripts/_diff-series.ts` (= 種2 差分抽出)
- `scripts/_select-supplement-diff.ts` (= 種3 fill 候補生成 = series-supplement.yml に未存在の key のみ抽出)
- `.cache/madb-last-release.txt` 初期化 (= 現在取込済 tag を記録)

これらが揃うまでは 「月次蒸留して」 を投げると Phase 0 で「対象が無い」 と abort される (= 安全側に倒れる、 想定通り)。

## 関連 commit

```
4402d3a  chore: register 月次蒸留 protocol in CLAUDE.md
153202e  data(seed3): batch 123/123 (= rank 12103-12202) FINAL 2000/2000
18097d8  data(seed3): batch 122/123 ... (以下 session 7 の 20 batch)
... (session 6 の 13 batch、 session 5 の 20 batch も同様)
```

## 次セッションでの推奨アクション (= 上書き)

種3 fill は 100% 達成済。 次は:
1. **月次蒸留 script 実装** = `scripts/_diff-madb.ts` / `_diff-series.ts` / `_select-supplement-diff.ts` の 3 本 + `.cache/madb-last-release.txt` 初期化
2. **Phase 5 (= Amazon PA-API)** = アフィリエイトサイト本格運用への移行準備
3. **frontend MVP 動作確認** = 70,202 件 fill 済 series-supplement.yml が反映された Next.js export の検証
4. **データ品質チェック** = 種3 fill 内容のサンプリングレビュー

---

# 種3 fill 作り方 (= 再利用 guide / 月次蒸留 & 新規シリーズ追加時)

種3 fill の **全 70,202 件は 2026-05-13 完了済**。 以降の新規 series 追加 (= 月次蒸留 で MADB に新着があった場合) や 表記揺れ修正時にはこの guide を踏襲する。

## 1. batch JSON 構造 (= 必須 dict 形式)

```json
{
  "Q<qid>|<base_title>": {
    "magazine": "<連載誌 string or null>",
    "demographic": "shounen | shoujo | seinen | josei | kodomo | other",
    "genres": ["<25 master keys から複数>"],
    "synopsis": "<1-3 文の要約>",
    "status": "completed | ongoing | hiatus",
    "anime_adapted": true | false
  }
}
```

**⚠️ NG パターン**: array 形式 `[{"key":...,...}]` は `_apply-fills.ts` が拒否し `applied=0, missing=100` を返す。 必ず dict 形式 (= key → object map)。 過去 session 34 batch 652 で誤って array 形式を提出し再修正した実例あり。

格納先: `data/seeds/_fills/batch-NNN.json` (= 一連の連番、 既存最終番号 = 705)。

## 2. 適用 flow (= per-batch protocol、 不変)

```bash
# 1) batch JSON を作る (= 100 entry / 1 batch を推奨)
# 2) 適用
npx tsx scripts/_apply-fills.ts data/seeds/_fills/batch-NNN.json
# 期待出力: [apply] done: applied=N, missing=0, total entries=70202
# missing > 0 なら原因解析 (= PUA 文字 / 表記揺れ / そもそも seed_keys に無い)

# 3) commit + push (= 各 batch を 1 commit で分離、 revert 容易)
git add data/seeds/_fills/batch-NNN.json data/seeds/series-supplement.yml
git commit -m "data(seed3): batch NNN/MMM (= sessionXX) Opus 4.7 直筆 fill"
git push origin claude/manga-database-affiliate-3x0ms
```

## 3. fill 候補抽出 (= 月次蒸留時の前処理)

```python
import yaml
with open('data/seeds/series-supplement.yml') as f:
    seed = yaml.safe_load(f)
unfilled = [s['key'] for s in seed['series'] if not s.get('synopsis')]
print(f"unfilled: {len(unfilled)}")
```

新規 series が追加された場合、 `series-supplement.yml` には placeholder (= key のみ、 synopsis 不在) で entry が増えているはずなので、 上記で抽出される。

## 4. ⚠️ PUA (Private Use Area) 不可視文字の特殊処理

**問題**: MADB raw データの一部 key には U+E000-F8FF 範囲の **不可視 PUA 文字** が混入。 例:
- `Q11268905|ウルフチックにお願い<U+E2BB>` (= 末尾に U+E2BB)
- `Q11621242|バージン<U+E2BE>ラブ` (= 中央に U+E2BE)
- `Q6359803|D<U+E203>j<U+E1F7> vu` (= 元 「Déjà vu」 の é/à 位置)

エディタ / ターミナル上では完全に見えないため、 **可視文字のみで keypath を書いた fill JSON は YAML 照合に失敗する**。 session 30-36 の 7 セッション連続で同じ 15 件が missing になり続けた原因。

**fix 手順** (= session 37 で確立):

```python
import yaml, json

with open('data/seeds/series-supplement.yml') as f:
    data = yaml.safe_load(f)

unfilled_raw = [s['key'] for s in data['series'] if not s.get('synopsis')]
for k in unfilled_raw:
    print(repr(k))  # repr で PUA 文字 \uXXXX が見える

# 生キー (= PUA 含む) をそのまま辞書 key として使う
fills = {k: {"magazine": None, "demographic": "...", "genres": [...], "synopsis": "...", "status": "completed", "anime_adapted": False} for k in unfilled_raw}

with open('data/seeds/_fills/batch-NNN.json', 'w', encoding='utf-8') as f:
    json.dump(fills, f, ensure_ascii=False)
    # ensure_ascii=False が必須 — 日本語生表記 & PUA 文字も保持される
```

**⚠️ 避けるべき**:
- Write tool / Edit tool 経由で batch JSON 内に PUA 文字を手書きしようとすると、 入力 stream で消滅する可能性が高い。 **必ず Python script 経由で書き出す**。
- visible-only な key path で書き上げた batch は missing>0 を必ず引き起こす。

### 既知の PUA 混入キー一覧 (= 2026-05-13 時点 15 件、 session 37 で fix 済)

| QID | 表示上のキー | PUA codepoint |
|---|---|---|
| Q11268905 | ウルフチックにお願い | U+E2BB (末尾) |
| Q11318682 | パニックパラダイス | U+E2BB (中央) |
| Q11460951 | どっちにするの | U+E2BB (末尾) |
| Q11460951 | わがままレイディ | U+E2BB (末尾) |
| Q11513040 | 猫と月チェイス | U+E2BB (中央) |
| Q11559342 | ちょっとでちゃった | U+E2BB (末尾) |
| Q11572016 | にゃんにゃんドリーム | U+E2BB (中央) |
| Q11621242 | バージンラブ | U+E2BE (中央) |
| Q11642002 | いずみタッチダウン! | U+E2BB (中央) |
| Q18236674 | ひとりにしないで | U+E2BB (末尾) |
| Q2731432 | キャンディキャンディ | U+E2BB (中央) |
| Q2928653 | むちむちパトロール | U+E2BB (中央) |
| Q2928653 | むちむち地球防衛隊 | U+E2BB (中央) |
| Q3100347 | Atta2 | U+E310 + U+E312 (「2」両側) |
| Q6359803 | Dj vu (← 元 「Déjà vu」) | U+E203 + U+E1F7 (é/à 位置) |

→ 月次蒸留で新たに PUA 混入 key が出現した場合、 同じ fix 手順を踏襲。

## 5. 効率化 tips (= 70,202 件実走で確立した patterns)

### Q-code cluster 単位で fill する
同一作家 / 同一原作の作品群は context が共通 (= demographic / genre / 系統が同じ)。 batch 内で一気にまとめて書ける。 例: `Q5xxx|藤子・F・不二雄` cluster の作品は全て shounen + comedy / sci-fi。

### demographic 判定の典型例
- `shounen`: 「ONE PIECE」「るろうに剣心」型 (= 少年誌掲載 / 主人公 10-20 代少年 / バトル・冒険系)
- `shoujo`: 「ガラスの仮面」「あさきゆめみし」型 (= 少女誌掲載 / 恋愛・ロマンス系 / 学園もの)
- `seinen`: 「島耕作」「美味しんぼ」「孤独のグルメ」型 (= 青年誌掲載 / 成人を主役)
- `josei`: 「Papa told me」「ダーリンは外国人」型 (= 女性誌掲載 / 成人女性主役)
- `kodomo`: 「ドラえもん」「アンパンマン」「コロコロ系」型 (= 児童誌掲載)
- `other`: 上記いずれにも当てはまらない場合のみ

### 特殊カテゴリ
- 成人向け / ecchi系 → `seinen` + `ecchi` genre tag
- 教育 / 学習 / 仏教 / 歴史教育 → `kodomo` or `seinen` + `educational` (or `religion`) genre tag
- レディコミ (= 成人向け女性誌) → `josei` + `ecchi` genre
- ハーレクインコミックス → `josei` + `romance`
- アンソロジー / トリビュート / 多作家集 → demographic は主流に合わせる

### anime_adapted の判定基準
- TV シリーズ / 劇場版 / OVA / Web アニメ化が確認できる作品 のみ `true`
- 確信がない場合 / オリジナルアニメは原作ではない場合 → `false`

### 報告頻度 (= ユーザ指示時)
- 100 batch / 500 件 / block 単位 等、 ユーザの指示頻度で JST timestamp 付き報告
- 例: `🎉 Block N/M 完了 (= X/Y = Z%) [JST YYYY-MM-DD HH:MM:SS]`

## 6. 関連 commit (= 全完了の trail、 抜粋)

```
4e7fc53  docs(memory): session 37 PUA fix 完了 → 真の100%到達 70202/70202
311b680  data(seed3): batch 705/705 (= session37 PUA fix) 真の100%到達
8c77406  data(seed3): batch 704/704 (= session36, FINAL 99.98%、 PUA 15件残)
... (batch 1-704 = sessions 1-36 の全 batch commit、 略)
4402d3a  chore: register 月次蒸留 protocol in CLAUDE.md
```

---

# 2026-05-17 セッション: path B' = 種2 rebuild プロジェクト (= A2.5)

## 経緯 / 動機

既存 種2 sqlite (= `.cache/db.sqlite`、 70,202 series) に **構造的 bug** 多数発覚:

1. `lib/edition.ts:baseTitle()` が ` : <副題>` を強制 strip → 「うる星やつら」 と
   「うる星やつら : オンリー・ユー」 「うる星やつら : 小説」 が **同 series に merge**
2. `title_kana` の選択ロジックが book 単位 任意採用 (= 多数決せず)、 結果
   「らんま 1/2」 の kana が `ランマ 1 2` (= 100 books 中 2 件しかない少数派) になる
3. `volumes.number` INTEGER で `上`/`下`/`特装版` を 強制数字化 (= 表示時に label 失う)
4. edition 分類が imprint base で粗い (= 小説版 / アニメ版 が standard edition に混入)
5. series.title に 副題本文 を保持せず (= 「ビューティフル・ドリーマー」 等 消失)
6. MADB schema:alternateName (= 公式英語題) を保持せず

そのため **path B' = 種2 を 別ファイル (= `.cache/db-v2.sqlite`) に rebuild** する大手術を実行。
旧 `.cache/db.sqlite` は **完全に不変**、 並走運用。

## 完成した成果物 (= 全 commit push 済 `claude/manga-database-affiliate-3x0ms`)

### scripts (= path B' pipeline、 順番に実行)

```
1. scripts/_build-series-v2.py     (= 種1 → 中間 JSON)
   - 入力: .cache/madb/metadata104.json (= MangaBookSeries 139k records)
          .cache/madb/metadata101-clean.json (= MangaBook 397k books)
          data/seed/mangaka.csv (= 9,562 mangaka with qid)
   - 処理: 
     Phase 1: metadata104 全件 cluster 化 (= 120,673 clusters)
              clustering key: (qid_or_creator_name, base_title, subtitle)
              副題は ` : ` 右側で 分離、 base に含めない
     Phase 2: metadata101 個別 book を Phase 1 cluster に linkage 
              (= name+creator match で 314,624 books 紐づけ = 78.8%)
     Phase 3: 紐づかない orphan books を 自前 baseTitle で 集約 
              (= 37,590 補完 clusters、 メジャー作品 HUNTER×HUNTER 等を救う)
   - 出力: .cache/series-v2.json (= 158,263 clusters)

2. scripts/_db-init-v2.py          (= sqlite 初期化)
   - 入力: db/schema-v2.sql + master yml/csv
   - 処理: 旧 db-v2.sqlite は backup .bak-* に退避、 空 db 作成、
          publishers/magazines/mangaka を seed
   - 出力: .cache/db-v2.sqlite (= 空 schema、 19 tables)

3. scripts/_populate-v2.py         (= cluster → sqlite)
   - 入力: .cache/series-v2.json + db-v2.sqlite
   - 処理: 158k clusters を series rows に投入、 
          editions は (type, normalize_imprint(brand)) で 集約、
          books は madb_book_id (= M-prefix) で 一意化、 ISBN なし volume も投入、
          normalize_imprint: 中黒/全角空白/半角空白 を 全除去 (例: 'ジャンプ・コミックス' = 'ジャンプコミックス')
   - 出力: db-v2 に 158,263 series / ~170k editions / ~381k volumes

4. scripts/_apply-adult-filter-v2.py  (= 5-signal adult filter)
   - 入力: db-v2 + data/seeds/adult-imprints.yml (= local)
          + data/seeds/adult-wikipedia-cache.yml (= GitHub Actions 由来)
   - 処理: 5 signal で adult_score 計算 + adult_signals 投入
     - madb_content_rating: weight=5 (= MADB schema:contentRating='成年コミック')
     - wikidata_hentai_credit: weight=2 (= mangaka.has_adult_credit=1)
     - wikipedia_adult_mangaka_list: weight=2 (= 2,035 名)
     - adult_imprint: weight=3 (= 235 件 yml seed)
     - adult_publisher_imprint: weight=3 (= 21 件 Wikipedia 由来)
   - 結果: 6,160 series が score>=3 (= 非公開)、 152,103 公開

5. scripts/_migrate-seed3.py         (= 旧種3 → 新 series_key)
   - 入力: 旧 data/seeds/series-supplement.yml (= 70,202 entries) + db-v2
   - 処理: 旧 key 「qid|baseTitle」 → 新 series_key (= db-v2.series.series_key)
          副題なし候補 優先、 副題 1 件のみなら 1:1 migrate (= "migrated_unique_sub")
   - 結果:
     - migrated 1:1   : 49,828
     - migrated unique sub: 997
     - orphan (= 旧 MADB 由来で 消失): 19,338
     - ambiguous     : 39
     - 出力: data/seeds/series-supplement-v2.yml (= 50,825 entries)
     - 出力: data/seeds/migration-stats.yml

6. scripts/_build-ai-fill-queue.py   (= 不足分 filter)
   - 入力: db-v2 (= 152k 公開) - series-supplement-v2.yml (= 50k 移行済)
   - 処理: need_fill (= 103,278 件) を isbn>=2 で filter
   - 結果: 25,617 件 = AI fill 対象 (= 257 batch、 概算 cost ~$591)
   - 出力: data/seeds/_ai-fill-queue.yml

7. scripts/_promote-bulk-v2.py       (= db-v2 + seed3-v2 → user yml)
   - 入力: db-v2 + series-supplement-v2.yml + 旧 data/manga/*.yml (= slug source)
   - 処理:
     - step A: 親 series 検出 (= 同 qid + title prefix + parent has more vol)
              → 子 series を spinoff 判定
     - step B: 本編 edition filter
              keep type ∈ {standard, bunkobon, wideban, kanzenban, shinsoban, aizoban}
              drop type ∈ {anime, other, renewal}
              drop imprint LIKE 'My first big%' / '%コンビニ%' / '%増刊%' / '%同人%'
     - spinoff series は max(release_date) >= CUTOFF_YEAR=2015 なら keep、 else drop
     - editions を 第1巻 release_date 昇順で sort (= 通常版→ワイド版→文庫版)
     - year_started = MIN year (全 volumes)
     - year_ended = 最初 edition の MAX year (= outlier 1件除外 = 末尾年が直前と5年以上空くなら drop)
     - status=ongoing なら year_ended=null
     - magazine/publisher key を master yml で validate (= 不正 key は src yml fallback)
   - 結果: 47 yml 生成 (= 9 件 spinoff/anthology drop)、 data/manga.v2/ に出力

8. scripts/_dump-adult-tables.py     (= GitHub Actions 用、 db → yml dump)
   - .cache/db.sqlite の adult_publishers/adult_mangaka_known を yml export

### GitHub Actions

- `.github/workflows/fetch-adult-lists.yml`:
  - サンドボックス (= Claude Code 環境) は Wikipedia 403 でブロック
  - GitHub clouds 環境で `npm run fetch:adult-lists` 実行 → 
    `data/seeds/adult-wikipedia-cache.yml` に commit
  - workflow_dispatch trigger で 手動実行
  - 既に 1 回実行済 → cache yml 存在
  - 月次蒸留時 再 trigger 推奨 (= Wikipedia 更新反映)

### schema 拡張

`db/schema-v2.sql` (= 旧 schema.sql は 不変、 並走):

```
series (21 cols):
  + source TEXT NOT NULL ('madb104' or 'orphan101')
  + subtitle TEXT
  + subtitle_kana TEXT
  + title_official_en TEXT
  qid UNIQUE 解除 (= 旧仕様だが実質 0 件使用、 path B' で 用途復活)
  series_key 形式変更:
    旧: norm:<baseTitle>|qid:Q…
    新: qid:Q...|name:<title>
        qid:Q...|name:<title>|sub:<subtitle>
        name:<creator>|name:<title>

editions (9 cols):
  UNIQUE (series_id, type, imprint)
  (旧 series_id, type のみ → ワイド版 etc 混在解消)

volumes (12 cols):
  + madb_book_id TEXT UNIQUE (= M-prefix、 ISBN なし book 用 dedup key)
  + volume_label TEXT (= '上'/'下'/'特装版' 等 生 label)
  isbn13 nullable (= 旧 NOT NULL UNIQUE 解除、 1980 年代以前 巻 対応)
```

## design review (= 7 Q 全部議論済)

| # | 項目 | 決定 |
|---|------|------|
| Q1 | series.qid UNIQUE 解除 | 解除 (= 1 mangaka が複数 series を持つため) |
| Q2 | series_key の source suffix | 案 c: suffix なし、 madb104 + orphan を 同 key で 統合 |
| Q3 | madb_series_ids の 持ち方 | series 列 削除 (= editions.madb_series_id で集計可能) |
| Q4 | editions.madb_series_id | 削除 + UNIQUE(series_id, type, imprint) (= 同 brand 重複 MADB record を merge) |
| Q5 | 同 series+type で複数 editions | Q4 で解決 (= 別 imprint なら OK) |
| Q6 | volumes.number + volume_label | INTEGER + label (= 強制数字化、 表示は label) |
| Q7 | orphan の magazine/demographic | NULL → 種3 fill (= 既存運用継承) |

## 現状: deploy + 視覚確認段階

- data/manga/ に 47 yml 配置済 (= 旧 data/manga.bak-* に backup)
- typecheck pass、 vitest 209 tests pass、 loadAllManga 47 entries 成功
- frontend deploy で 視覚確認できる状態
- ユーザ 確認済の 主要 series:
  - うる星やつら: 1980〜1987 完結、 通常版 34 + ワイド版 15 + 文庫版 18 ✅
  - らんま1/2: 1988〜1996 完結、 kana=ランマ ニブンノイチ ✅
  - ハイキュー!!: 2012〜2020 完結 (= imprint 中黒違い 統合 fix で 直った)

## 未解決の課題 (= 次セッション で 続行)

### 🔴 重要

1. **mezon-ikkoku / doragon-booru 等で year_ended が 過剰** 
   - mezon-ikkoku: 1982〜2007 (= 期待 1987)
   - doragon-booru: 1986〜2004 (= 期待 1995)
   - 原因: 複数巻の 1980 年代 ISBN が MADB に なく、 リニューアル版 (2000s) ISBN のみ
   - 「outlier 1件除外」 logic では救えない (= 多数巻が同様パターン)
   - 案: 1990年代初版の ISBN-10 を ISBN-13 化 で別ソース取得 / 種3 に year_ended 追加
   - 影響: completed 旧作品 (= 1990 年代以前) の 一部 で 同様パターン

2. **AI fill 25,617 件 (= ~$591) 未実施 (= step I)**
   - data/seeds/_ai-fill-queue.yml に 候補リスト準備済
   - 巻数最多 鬼平犯科帳 329、 美味しんぼ 244、 キン肉マン 166 等 メジャー作品多数
   - これらは 旧種3 でも 一部 fill 済だったが creator name 違い cluster で migration 失敗
   - source 内訳: madb104 16,402 + orphan101 9,215
   - 旧 MEMORY.md 末尾 「種3 fill 作り方」 セクション の protocol で 実行可能

3. **「creator merge logic」 未実装**
   - 鬼平犯科帳 が 4 cluster (= 池波正太郎/さいとう・たかを/さいとうたかを/大原久澄)
   - 同一作品の 原作者 vs 漫画家 別 attribution で 別 cluster 化
   - merge 実装で AI fill 件数を 数千件削減可能
   - heuristic: 同 base title + 同 qid 候補 multiple → merge?

### 🟡 中程度

4. **edition imprint 表記揺れの 更なる統合**
   - 中黒/空白 strip は 実装済 (= G.6 fix)
   - 残: 「Big comics」 vs 「ビッグコミックス」、 「Jets cimics」 vs 「Jets comics」 等
   - 解決案: ISBN prefix から publisher 推定、 同 publisher の imprint variation を 統合

5. **「マンガその他」 (= metadata103) leak 経由の関連書**
   - うる星 だと 「『うる星やつら』の秘密」 が madb104 にも あるため leak
   - 関連書 keyword filter (= 'ガイド'/'画集'/'ファンブック' 等) 実装案あるが 未適用
   - 影響: 47 promoted yml には 直接影響少ない (= step A spinoff filter で大半 catch)

6. **brand → magazine 静的 mapping (= option D from Q7)**
   - 現状: magazine/demographic は 種3 経由のみ
   - 未 fill series は magazine=null 表示
   - data/seeds/brand-to-magazine.yml 等 新設で 自動推定可能 (= 100~200 brand 手書き)
   - 優先度: step I 完了後で再検討

### 🟢 低

7. **腎臓盤 (= step B filter) の枯渇候補**
   - drop pattern: 'My first big%' / '%コンビニ%' / '%増刊%' / '%同人%'
   - 「BOOK」 「スペシャル」 「プレミアム」 等 1,400+ 件 microscopic candidates 残り

8. **MADB 表記揺れの追加 fix (= 旧 cluster 残骸)**
   - 「英訳・うる星やつら」 「劇場版犬夜叉時代を越える想い」 等 接頭辞付き title が
     parent 検出失敗で 「本編 spinoff」 判定漏れ
   - title normalize で 接頭辞 strip 実装案あるが 未適用

9. **smiloid 鬼平犯科帳 など Mangaka.csv 未登録**
   - 「綱本将也」 (= GIANT KILLING 作者) が mangaka.csv に居ないため orphan
   - 大原久澄 等 同様
   - 解決案: mangaka.csv 拡充 (= 種1 強化)、 月次蒸留 protocol で fetch:mangaka 再実行

### ⚪ 設計レベル

10. **promote-bulk-v2 が 既存 56 yml のみ regenerate**
    - 全 152k 公開 series → yml は 別作業
    - data/manga/_drafts/ に 大量生成 → 人手 review 経由運用 (= 旧フロー)
    - 現状 47 yml は 視覚確認用

11. **deploy 確認 未完**
    - frontend は Cloudflare Workers (= huichi0725.workers.dev)
    - ユーザが 各 fix 後 手動 deploy + 視覚確認
    - 最後の確認: 2026-05-17 ハイキュー fix push 後

## 主要 commit (= path B' trail)

```
806f637  fix(G.6): imprint normalize で 中黒・空白違い edition を 統合
fac97e0  fix(G.5): year_ended で outlier 1件除外で 全 yml 改善
c244aa3  fix(G.4): year_ended を 本編原作完結年で 算出
ec28539  fix(G.3): edition 順序 + ISBN なし volume 投入 (= fix 2)
bd158be  feat(G.2): step A/B filter で 「本編以外は極力非表示」 適用
4bda25d  feat(G+H): data/manga/ を v2 出力で置換 + validate fix
0ce98fb  feat(G): _promote-bulk-v2.py で v2 yml 生成
ef03e39  feat(F.2): migration 改善 + AI fill queue 生成
164a7dd  feat(F): _migrate-seed3.py で 旧種3 70k → 新 series_key
5d09e41  feat(E): _apply-adult-filter-v2.py で adult filter 5 signal 適用
fa6ca58  chore(E.prep): GitHub Actions で Wikipedia adult lists fetch
0ba6177  feat(D): _populate-v2.py で db-v2.sqlite に 158k series 投入
562087b  refactor(C.2): schema-v2 で editions.madb_series_id 削除
0415a4b  refactor(C.1): schema-v2 で series.madb_series_ids 削除
017d530  feat(C): db/schema-v2.sql + scripts/_db-init-v2.py
75c1418  fix(A.3): creator name normalize 強化で cluster 分裂 改善
b5d91ef  feat(A.2): _build-series-v2.py hybrid 化 (= option A)
5aba001  feat(A): scripts/_build-series-v2.py + .cache/series-v2.json
afffd82  chore: subtitle-review scaffold 破棄 (= path B' へ戦略変更)
```

## 次セッションでの推奨 スタートアクション

1. **MEMORY.md 読了** (= このセクション)、 CLAUDE.md 読了
2. `git pull origin claude/manga-database-affiliate-3x0ms` で最新取得
3. ユーザの 視覚確認 結果 を 聞く (= deploy 後の MANGAL 画面で 47 yml が どう見えるか)
4. 残課題から 優先順位を 聞いて 着手:
   - 「mezon-ikkoku / doragon-booru year_ended 問題」 を fix するか
   - 「step I (= AI fill 25k 件) を 始める」 か
   - 「creator merge logic」 を試すか
   - 別のメジャー作品 (= ジョジョリオン / ベルセルク等) を 視覚確認する

## 重要設定値

```python
# scripts/_promote-bulk-v2.py
CUTOFF_YEAR = 2015  # spinoff で この年以降なら keep
KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
DROP_IMPRINT_PATTERNS = ["My first big", "コンビニ", "増刊", "同人"]
```

## 重要な user 意図 メモ

- 「本編 = 通常版 + ワイド版 + 文庫版 + 完全版 + 愛蔵版 + 新装版」
- 「アニメ版 / 廉価版 / 関連書 / 別作品コミカライズ は 表示不要 (= 最近 物は除く)」
- 「CUTOFF_YEAR で 古い spinoff は drop、 最近 は keep」 という方針合意済
- edition 順序: 第 1 巻 release_date 昇順 (= 通常版→ワイド版→文庫版)
- year_ended: 本編原作完結年 (= リニューアル版 含めない)
