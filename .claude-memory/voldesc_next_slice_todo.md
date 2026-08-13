---
name: voldesc_next_slice_todo
description: "巻説明seedの現在地(11,504件)と、次に「巻説明つくって」で再開する手順・並列運転の型"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3e3a9f98-da9d-4815-a148-8c58f6e055f6
  modified: 2026-08-13T04:49:59.168Z
---

**現在地(2026-08-13)**: `data/seeds/volume-desc-ja.jsonl` = **11,504件**(この日の30分並列で +887)。
既存ジョブ在庫は消化済み。次は**a系の続き(akagami以降)**から。

## 再開手順(そのまま踏めば動く)
1. `cp .cache/voldesc/materials.jsonl .cache/voldesc/materials-R<N>.jsonl` ← ★必ずスナップショット。
   `_par_check.py` が `materials*.jsonl` を全部舐めてISBN→(slug,vol)の真値にするので、上書きすると過去ジョブが検証不能になる。
2. `python scripts/_voldesc-material.py --local-only --take 8000` ← ★**--takeは大きく**。
   小さいと(--take 400等)アルファベット頭の枯れた区画しか見ず「材料なし390/403」になる。8000で **caption有 2,989** が出た。
3. `python scripts/_par_prep.py` → `.cache/voldesc/par/<slug>[-pN].txt` が生成される。
4. 残量ランキングを出して**多い順に20並列**へ(seed既存ISBNを引いた実残数で並べる。par内の巻が全部seed済みのファイルが混ざる)。
5. 各エージェントは **`.cache/voldesc/out/w<ラベル>-<slug>.jsonl` に書くだけ**。apply/gitは絶対にさせない。
6. 親が `python scripts/_par_check.py`(ALL_OK確認)→ `python scripts/_voldesc-apply.py ".cache/voldesc/out/w*-*.jsonl"` → commit+push。

## 実測の型(2026-08-13)
- 1エージェント ≒ 17〜24巻を **1〜3.5分**。20並列で **約350〜450巻/波**。
- 丸写しreject率は **1%未満**(887件中4件)。書き直しは ①主語替え ②文順入替 ③体言止め分解 ④長い連続句を2文に割る で全部通った。
- ★**applyのglob再実行で古いrejectが再表示される**: 修正版は別ファイル(`w30-fix1.jsonl`等)に書くため、元ファイルの不良行は残ったまま毎回rejectログに出る。**seedに入っているかをISBNで確認すれば足りる**(消し込み不要)。
- ★**エージェントに渡すISBNリストを手打ちするな**: blue-rokku宛に別作品(異世界魔王)のISBNを渡してしまい、エージェントが照合して拒否した。残ISBNは必ず**seedとparファイルの差分をスクリプトで算出**して渡す。

## 材料が無くて書けない典型(スキップは正しい挙動)
特典・限定版告知のみ(ドラマCD/DVD/アクスタ/ステッカー)、シリーズ共通惹句のみ、収録話タイトルだけ、刊行案内・累計部数のみ。
→ **無理に書かせない**(水増し・捏造になる)。`no-material.txt` 台帳に積まれ、Sonnetのアイドル運転(柱⑦ `--recheck-nomaterial`)がliveで敗者復活させる。

関連: [[feedback_accuracy_is_the_goal]] [[voldesc_finish_started_series.md]] [[feedback_no_popularity_priority]]
