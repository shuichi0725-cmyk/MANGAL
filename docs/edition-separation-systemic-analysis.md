# 版分離 systemic 化 分析（2026-06-23）

## 問題
奇子型（同一著者の版違い混在）= promote が **同 type(standard等) の版を imprint 跨ぎで1つに畳む**ため、
別出版社の巻が混ざって scramble する。ayako-candidates に約1,562作、editions-supplement で手修正は7作のみ。
「手で1つずつは続かない」（ユーザ指摘）。

## 現状の promote ロジック
- `_promote-bulk-v2.py` L1518〜: 種2の各 edition(edition_id)を読み、L1583 `group_key = effective_type` で
  **type単位に畳む**（最古を正典表示）。blanket分離は古典の重版爆発を避けるため opt-in(`separate_editions`)。
- `separate_editions` フラグは実装上 **(type × 種2 sid)** でグループ化(L1585) = 単一sid内の複数imprintは分離しない
  → 菜/手塚（1sidに複数版）には効かない。

## データ実態（.cache/db-v2.sqlite、巻ありseries 132,588）
- **1版: 122,673 (92.5%)** — 畳む/分離どちらでも無影響
- 2版: 7,561 / 3版: 1,454 / 4版: 486 / 5版: 228 / 6版以上: 149
- 多版（畳むと scramble しうる）= 約 **9,915作**

## ヒューリスティック検証: (type × ISBN出版社prefix) で畳む
多版9,915作に適用した結果:
- **1版に吸収: 4,414 (45%)** = 同社のラベル表記揺れ（例 ぱすてる「SHONEN MAGAZINE COMICS」「少年マガジンコミックス」「講談社コミックス」全部978406）を正しく統合 = **過剰分割しない**
- **複数版に正分離: 5,501 (55%)** = 本当に別出版社（例 キャラバン・キッド=白泉社978459＋小学館978409）= 奇子型を**自動修正**
- 畳み後の版数分布: 1版4,414 / 2版4,437 / 3版790 / 4版178 / 5版59 / 6版以上37
- **爆発(6版以上)は37作のみ** = 例外処理（cap or 同社畳み）で対応可

## 結論・推奨
**promote の group_key を `type` → `(type × ISBN出版社prefix)` に変える**のが systemic 解:
- 約5,500作の奇子型 scramble を自動修正
- 同社ラベル揺れは畳む（過剰分割なし）= edition_id 直使いより優れる
- 92.5%は無影響、爆発は37作

### ただし systemic 解が**カバーしない**もの（editions-supplement 等で別途）
1. **resolve-master 注入** = 種2に無い harvest 由来ISBNが版に紛れる（菜の玄光社巻型）。種2 edition のグルーピングでは直らない。
2. **種2 mis-clustering** = 別作品が1 sidに誤統合（菜～ふたたび 講談社版が菜sidに）。クラスタ層の問題。
3. **出版社 rebrand / 多prefix版** = 角川書店→KADOKAWA(同prefix=OK)、朝日ソノラマ↔朝日新聞、1版が2prefix跨ぎ等のエッジ。
4. **同社内の特装/premium** = プレミアムKC 等を分けるべきか（現案では畳む）。

### 実装リスク
promote の版構築変更は全69k頁の edition 構造に影響。**小サンプルで dry-run → diff 確認 → 段階ロールアウト**必須。
後段 `_regroup-versions.py`（同type同巻数を刷タブに畳む）との相互作用も要検証。

### 推奨ステップ
1. promote に `(type × pub_prefix)` グルーピングのオプション実装（既存 separate_editions の改良 or 新フラグ）
2. 既知の手修正7作 + ayako サンプルで dry-run、editions-supplement 結果と一致するか検証
3. 一致率・爆発作を確認後、default 化を判断
4. editions-supplement は「注入/mis-cluster/手検証作」の例外ツールとして残す
