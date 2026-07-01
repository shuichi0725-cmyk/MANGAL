---
name: publisher_model_edition_level
description: publisher設計(b)=版ごと当時社名(事実)+work.publishers社キー集合。families不採用、実体=ISBN出版者記号で統廃合に強い。蒸留は自動導出+新社flag
metadata: 
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

publisher は **版(edition)ごとの事実**として持つ(設計(b)、2026-06確定)。「1作=1社」を強制した旧schema(work.publisher単一必須)が迷走の根源だった。

## 層
- **edition.publisher** = その版の**当時の生社名**(例「角川書店」「エンターブレイン」)。事実・不変・タブ表示。由来=**種2 ISBN → metadata101 schema:publisher**(巻ISBN群の最多社名)。
- **work.publishers[]** = 全版の**社キー** distinct(フィルタ用、複数社作品を捕捉。例 angel=[shogakukan, schubert-shuppan])。
- **work.publisher** = 代表=最多巻の版の社キー(ヘッダ表示)。1社も解決できねば`(unknown)`。
- **種3 は publisher を持たない**(ISBNから再生成可能 → 焼かない原則。[[synopsis_ja_seed]]と対照)。

## 名前→キー解決
- `data/publishers.yml`(161キー、display名=生社名)→ promoteが`norm()`照合で自動マッチ。
- `data/publisher-aliases.yml`(norm社名→キー)= **別名で同一実体のmergeのみ**。根拠=**ISBN出版者記号(帯)**で確認(角川書店/角川グループ→kadokawa[404帯]、エニックス→square-enix[47575]、リブレ出版→libre[4799]等)。
- ★**ISBN-10/13混在**注意: metadata101は古書ISBN-10、DBはisbn13 → `_to_isbn13()`で13正規化して突合(忘れると古い作品が全部pub=None)。
- 巻被覆93.4%。残り未キー=<200巻の極小社=editionに生社名表示のみ(フィルタ非対象でOK)。

## ★統廃合に強い理由(ユーザ懸念への回答)
- **families.yml/企業グループ畳みは不採用**。キー=登録実体(ISBN帯)であって親会社でない。エンターブレイン(4757)はKADOKAWAに吸収されても別キーのまま=過去データ貼り替え不要。
- A社→B社統合は「各版が当時名で別editionとして残り、版タブで両方出て入手可能性が自然にシフト」=事実に忠実。

## 蒸留での扱い
- promoteが**自動導出**(手動ステップ無し)。種2/aliases更新で全派生再生成される。
- ★**月次サニティ**: 新規の未キー社名(norm未解決)を巻数順にflag → 主要なら publishers.yml にキー追加。新aliasは**ISBN帯一致で同一実体を確認した時のみ**(だろう運転禁止)。
- 生成器: `scripts/_gen-publisher-keys.py`(キー+alias生成・被覆検証)。

実装commit b6c960fe(2026-06)。frontend: filters=版集合一致、MangaCard/作品ページ=代表キー→名。
