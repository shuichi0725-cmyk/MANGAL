---
name: author_pollution_overlay_fix
description: 著者汚染の根本原因(clean工程が[著]/[編]タグstrip→build役割優先が死にコード化)と overlayでの修正状態(author-role-corrections.yml)。dryrun検証済・本番未適用
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★**根本原因(2026-06-09特定)**: `scripts/clean-madb-seed.ts` が生MADBの `schema:creator` から `[著]/[編]/[解説]` 等の**役割タグをstrip+カンマ分割**(L100-110、設計者は正規化のつもり)。その結果 `_build-series-v2.py` L113 の「[著]/[作]を優先採用」ロジックが**死にコード化**→ タグ無し扱いで position[0] を採用→ **声優[解説]/編集[編]/発売元[発売]まで「作画」に潰れ、本編から分裂**。**汚染と分裂は同一原因の双子**。MADBは正しくタグ付けしていた(我々の喪失)。[[author_roles_state]] の「101-cleanが役割タグを剥がす」の全容。

**生タグの実態**(`scripts/_build-madb-role-map.py` が生metadata101から復元、`.cache/madb-mid-roles.json` 383,999件):
- 著者系 [著]278k/[原作]64k/[漫画]32k/[作画]16k/[画]11k/[キャラクター原案]9k…
- 非著者系(汚染源) [発売]22k/[頒布]7k/[編]7k/[監修]4k/[訳]3k/装丁系3.7k/[解説] + 地名ゴミ([東京]等)

**修正(overlay方式、種2不変)= ★本番v2適用済(2026-06-10):**
- `data/seeds/author-role-corrections.yml`(20,959補正: credits5,110系/5,692 + 原作化16,381系/18,638 + 救済163 + ガード)。series_keyキー=安定。生成器=`_gen-author-role-corrections.py`(全152k series・役割分類器=区切り分割+厳密照合)。
- `_promote-bulk-v2.py` `apply_author_corrections`(get_authors直後フック): 非著者role除去 + 原作系を role=original_author(→original_authors欄) + 救済add(マスター実在の非entity人物・変種重複除外)。**2層の空著者ガード**(生成時+promote最終安全網)。`get_author_credits`→`o["credits"]`。
- **credits欄新設**(著作でない 編/監修/訳/装丁/解説/企画/協力 を**捨てず役割付きで保持**): `schema.ts` CreditSchema / 詳細ページ「その他」欄 / `filters.ts` matchText の**キーワード検索haystackに著者+原作+credits名追加**(従来タイトルのみ)。著者フィルター/50音索引は**著者のみ**=credits は kana 不要。
- 検証(本番manga.v2): DEATH NOTE=小畑健[作画]/大場つぐみ[原作]、ドラえもん=藤子のみ著者+声優14名は解説credit、男どアホウ甲子園=水島新司/佐々木守/ダンカン他解説。空著者0・tsc/test通過。

**残(別タスク):**
1. ベルセルク型続編統合は**不要**と判明(promoteが既に統合済、本番berserk.yml=vol1-43一体)。続編merge候補3,400は誤検出で、本番実分裂は96=アンソロ/slug表記揺れ([[clustering_unit_is_series]])。
2. credits判定器の端タグ漏れ(共訳/DTP/カバー絵→authorに残る少数)、`(漫画)`丸括弧は対応済。
3. 版違い統合 / アンソロ方針 は未着手(構造の未決、要実スケール測定)。

関連: [[clustering_unit_is_series]](著者をクラスタ軸にした分裂の根本)/ [[madb_native_series_structure]] / [[author_roles_state]]。
