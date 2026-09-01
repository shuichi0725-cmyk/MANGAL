---
name: external_enrich_state
description: "【進行中】外部エンリッチ(skill external-enrich)の対象リストと進捗。2026-09-01時点: 5巻以上×2010年以降=消化済(残40=ほぼ保留)、5巻以上×2009年以前=1,285件中36行処理済み。次バッチ番号=9436"
metadata: 
  node_type: memory
  type: project
  originSessionId: ffbe783f-3849-4cd8-936a-578c71df6d9a
  modified: 2026-09-01T13:21:07.974Z
---

楽天captionが枯れた層に **Wikipedia + 魚(TinyFish)** の一次情報でキャッチ/詳細を付ける柱。
**やり方は skill `external-enrich` が正本**(トリガー「外部エンリッチして」「外部エンリッチ続けて」)。
ここは**状態(どこまでやったか)だけ**を持つ。

## 対象リスト(生成器 = `scripts/_enrich-backlog-scan.py`)

| リスト | ファイル | 状態(2026-09-01) |
|---|---|---|
| 5巻以上 × 2010年以降 | `docs/production-diagnostics/enrich-backlog-5vol-2010.tsv` | 230件→**残40**。うち39は保留台帳掲載済み(材料なし/境界)。実質完了 |
| 5巻以上 × 2009年以前 | `docs/production-diagnostics/enrich-backlog-5vol-pre2010.tsv` | **1,285件中36行処理済み(付与28作/保留8件)**。★ここから再開 |

再開の起点 = pre2010リストの **37行目**から。`WL_TSV=<pre2010.tsv> python scripts/_enrich-worklist.py 37 54`。

## 使用済みバッチ番号

**9401〜9435 使用済み → 次は 9436**。生成物 = `data/enrich-out-2026-07/batch-94NN.json`(git追跡)、
材料 = `.cache/enrich-batches/batch-94NN.json`。

## 実績(2026-09-01)

- 2010年以降リスト: **105作**に付与。副産物で誤りを4件是正(pokkapoka/デュエマVS/それでも僕らはヤってない/BOY)。
- 2009年以前リスト: **28作**に付与(代紋TAKE2・ドカベンプロ野球編・750ライダー・大甲子園・サーキットの狼・将太の寿司 等)。
- 掲載境界は**16頁をdrop実行済み**(ユーザGO 2026-09-01)。詳細は [[drop_batch_2026_09_01]]。

## 保留台帳(= 次に人が裁くもの)

`docs/production-diagnostics/enrich-hold.tsv`。2026-09-01時点で **未裁定の境界3件**:
ジャンプ放送局(読者投稿コーナーの単行本化)/絶対麗奴(著者8名)/ほんとにあった怖い話(実話怪談誌のコミックス)。
+ keepにした2件 = オリンポスの咎人(ハーレクイン連作。同系95頁が通常掲載)/今でも忘れられないアノ体験談(廉価版の断定材料なし)。

## 進め方のメモ(数値実感)

- 巻数の多い順に処理する。**20巻以上は有名作でWikipediaがよく当たる**=歩留まり高。
- 5〜9巻帯(961件)は「巻数はあるが情報が無い」青年誌・レディコミが増える=holdが増える見込み。
- 1回18〜20行、うち書けるのは **10〜17作**。残りは境界か材料なし。

関連: [[enrich_newest_seam_exhausted]] [[enrich_7k_resume_state]] [[catch_synopsis_enrich_pending]]
