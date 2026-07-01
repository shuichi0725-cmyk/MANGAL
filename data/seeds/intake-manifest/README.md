# intake-manifest = 統合台帳 (= 全操作の記憶)

設計: `docs/intake-manifest-gate-design.md`。本ディレクトリはその **実体(Phase 0)**。
目的 = 「何を・なぜ・どこから・どう検証して・何が残っているか」を**1か所**に永続化し、
次回蒸留/別PC/別日でも**総当たり再探索を消す**。散在していた18個の `*-changelog.jsonl` を束ねる。

## 構成

| ファイル | 中身 | 再生成 |
|---|---|---|
| `operations.jsonl` | 全cleanup/intake操作の統合ログ(1行=1操作) `{op_source, slug, related, at, raw}` | `scripts/_manifest-consolidate-ops.py` (= 各 `*-changelog.jsonl` から集約) |
| `holes-snapshot.jsonl.gz` | 全ページの穴 snapshot(provenance簿記) `{slug,title,status,vols,year,holes[]}` | `scripts/_intake-manifest-audit.py` (→.cache→gzipで永続化) |
| `holes-summary.json` | 穴のfield別/severity別 集計(軽量・状態把握用) | 同上 |
| `README.md` | 本書(運用protocol) | 手動 |

> ⚠️ `operations.jsonl` は**再生成不可の記憶**(=git必須)。holes は**再生成可**(script在git)だが、
> `.cache`置きだと消えるので **gzip snapshot を git に残す**(= 過去 .cache 消失で「あるはずなのに無い」事故を防止)。

## 運用 protocol (= 厳守、 CLAUDE.md にも転記)

1. **本番ページ(`data/manga.v2` / `.preview-data`)を触る操作は、必ず操作専用の `*-changelog.jsonl` に1行記録**
   (= 既存慣習。 slug / 操作 / before→after / at / 可逆backup を含める)。
2. **節目で `python scripts/_manifest-consolidate-ops.py` を回し `operations.jsonl` を更新** (= 統合台帳に反映)。
3. **大きめ作業の後 `python scripts/_intake-manifest-audit.py` で holes を取り直し**、
   `holes-snapshot.jsonl.gz` と `holes-summary.json` を更新 (= 穴の現状＝次の作業リスト)。
4. **新しい cleanup を始める前に台帳を見る** (= `operations.jsonl` で既処理か確認、 holes で穴確認)。
   → 「あるはず」を毎回 grep でなく**台帳で**確認する。
5. 人手可読の個別サマリ (例 `docs/isbn-unmerge-ledger.md`) は本台帳の**ビュー**。台帳が一次ソース。

## 参照

- 設計書: `docs/intake-manifest-gate-design.md` (型分類器 §2 / 必須マトリクス §3 / 出荷ゲート §7)
- un-merge 人手台帳: `docs/isbn-unmerge-ledger.md`
- 穴の層: T0=スキーマ床(loader拒否=本来0) / T1=品質blocker / T2=warn(出してよいが追跡)


## 2026-07-02 運用改善 (= 「手動で節目に」が回らず台帳が死んでいた対策)

- ★**自動集約**: `scripts/_reflect-targeted.py --push` が push 前に `_manifest-consolidate-ops.py` を自動実行。
  通常の反映フローに乗るだけで operations.jsonl が最新に保たれる (= 手動ルール2の形骸化を封鎖)。
- ★**クエリツール** `scripts/_ledger.py <slug>` = 「このslug過去に何した?」を一発で引く
  (op_source別サマリ + 各種別の最新 + holes状態)。 `--stale` = 未集約changelogの検出。
  ルール4「cleanup前に台帳を見る」の実行手段 (9千行の目grepは形骸化するため)。
- ★**版修正の2系統注意**: `edition-canonical/*.yml` 結線slug (golgo-13 / tsuribaka-nisshi) は
  edition-overrides.json を直しても**canonicalが後勝ちで無効**。reflect が警告を出す。
