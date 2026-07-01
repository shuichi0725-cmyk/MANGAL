---
name: page_dedup_2026_06
description: 重複ページdedup完了(335件統合、69,474→69,139)。根本原因=種2断片を旧sourceページ2枚が再集合し同一内容を二重出力。残=FLAG367(同ISBN別title)/C2別コミカライズの副題欠落
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★**2026-06-10 完了**: 本番の「中身が完全同一の二重出力ページ」**335件を統合**(manga.v2 69,474→69,139)。種2不変・情報ロスゼロ。

**根本原因**: 種2に同一作品のクラスタ断片(qid無orphan+著者集合違い)が残存 → 旧 `data/manga` の sourceページ(旧buildのslug揺れ `-2`/`o↔wo`/`ki↔koryakuki`)が2枚生存 → promoteの`find_related_series_ids`が**どちらからも同じクラスタ全体を再集合** → 同一内容の2ページ。★**slug揺れは症状、源はsource重複**。続編統合(ベルセルク型)・版違い統合と誤認していた問題の正体がこれ([[multi_edition_unification_pending]]の実測参照)。

**実装**(全て可逆):
- `scripts/_dedup-pages.py` = 検出器(★**ISBN集合の完全一致+同一title**=最保守。vol数不一致は自動処理から除外)
- `data/seeds/page-dedup.yml` = 335件(drop→canonical、根拠付き)。canonical選定=suffix無し優先→短い→辞書順
- `data/slug-aliases.yml` +335 → `public/_redirects` 301(=「消えたのでなく統合」の記録、旧URL生存)
- promote `_load_page_dedup` → source skip(再発防止)

**本番の同題複数ページ全調査の結論**(69,474ページ、dup-survey):
- A 副題違い10 = 正当 / ★**B 同名別作品952 = 正当**(BOX/HAL型、別ページが正しい=触らない)
- C 真の重複(今回統合) / **C2 ≈39 = 正当な別コミカライズ**(安達としまむら まに版vs山内版、魔法科5スピンオフ、人間失格3版)。★ただし**副題欠落で同題表示=見分け不能**→副題復元が別課題
- D 続編分裂2 = 軽微

**小粒掃除(2026-06-10 第2弾)**: ⑤怖い話=27巻側が完全上位集合と機械確認し統合。④FLAG367を特性化→**表記揺れ(NFKC正規化一致)57群/70頁のみdedup適用**(ISBN集合+vol数一致を再検証、除外0)。本番=**69,068**(累計405+alias422転送)。

**★ISBN混線の全数解消(2026-06-10 完了)**: 規模測定(isbn-multihome、本番全69k)で**572グループ/4,037重複ISBN/1,181ページ**を検出 → 重複ISBN3,733をNDL照会(`.cache/ndl-by-isbn.json`計10,719=恒久キャッシュ)→ 機械判定+三重検証で適用: **①subset統合166ページ**(本番69,068→**68,902**、page-dedup.yml計572+alias計588) **②ISBN振り直し1,010**(slug-volume-final.tsv計1,253行=slug適用時に反映。既存矛盾10は魔法科map/option2優先で除外) **③保留252=現状維持で本番に残す**(`data/seeds/_mix-review-pending.json`に永続化、後日個別判断=ユーザ確認済)。魔法科(98冊→14ページ)も同経路で解決済。分離キー=レーベル整理番号連番(電撃N190等)+NDL真title。

**★罠(2026-06-16): page-dedup × slug-override の不整合で本編消失**。page-dedupは `drop:slug / canonical:slug`。後から [[slug_apply_pipeline]]/slug-overrides で **canonical側のslugを改名**すると(例 meitantei-conan-2011→meitantei-conan)、canonicalが存在しなくなり drop側(本編 meitantei-conan)が**宙吊りで本番から消える**。再promote後は「主要作品が出ているか」を必ず確認。修正=stale dedupエントリ除去 or canonicalを実在slugへ付替。[[slug_cluster_fix_and_changelog]]

**残課題**:
1. **保留252**(_mix-review-pending.json) = 別作品subset疑い/NDL判定不能(漫画版世界の歴史/ギリシア神話群/Joker等)。後日個別。
2. FLAG難物の残り(Ar tonelico vs 2等の部分一致) = 大半は上記①②で解消済みのはず、残りは保留252と重複。
3. C2の正当別コミカライズ(安達としまむら等)の表示区別(著者/出版社で区別可、title同一は仕様内)。
