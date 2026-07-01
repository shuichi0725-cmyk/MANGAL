---
name: series-fragmentation-rootcause
description: "series 分裂(SLF が4 sid 等)の根本原因と ndla 著者集合ベース統合案。全DB約1万作品が分裂、sim で9,969 group統合可能"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

series 分裂問題の構造解析(2026-05-30 夜間自走)。 詳細レポート = `docs/series-fragmentation-analysis.md`。

**現象**: シャングリラフロンティアが同一作品なのに 4 series_id に分裂(sid 77559/141297/141298/141299)。 SLF 固有でなく**全 DB で約 10,018 作品 / 20,962 series 行**が分裂(ゴルゴ13・美味しんぼ・うる星・タッチ・はじめの一歩・コナン等)。

**根本原因**: `_build-series-v2.py` 行316 のクラスタキー = `(単一著者 or qid, 生 base_title, 生 subtitle)` の完全一致。 4 軸で割れる = ①著者キーの並び順依存(原作 vs 作画 vs qid-vs-name)②subtitle 有無 ③title 中点/スペース揺れ ④subtitle 末尾ピリオド。 c27c049 で `authors`(series_authors)は ndla 名寄せで安定化したが、 **クラスタ判定には意図的に未使用**(series_key を Wikidata-only 凍結 = 種3 保護)。 [[madb-native-series-structure]] の続き。

**頑健軸**: ndla 名寄せ済 `dcterms:creator` 著者集合(既に series_authors に計算済)。 SLF 全25巻で `{硬梨菜, 不二涼介}` が完全一致。 isPartOf 容器は 5/25 しかカバーせず補助止まり。

**promote 層の欠陥**: `find_related_series_ids` の統合キーが qid / 完全一致 title 依存 = 分裂原因そのもの。 著者集合を merge キーに使っていない。

**提案(案A 推奨)**: build の series_key は不変のまま、 `series-merge.yml` に `merge_sids:` を自動注入(既存機構が promote/audit で読む、 完全可逆、 種2/種3 不変)。 grouping = `(著者集合, 正規化title)`、 subtitle が semantic marker(第/部/編/外伝/番外/章/完結)を含む group は auto 統合せず保留(別ページ維持が正当 = 釣りバカ番外編等)。

**sim 実測** (`scripts/_sim-author-set-merge.py`, 出力 `.cache/proposed-author-set-merges.json/.csv`): auto統合 9,969 group(series 20,841→9,969 = 10,872削減)/ 保留 56 group。 SLF・美味しんぼ・代紋は正しく集約、 番外編類は正しく保留。

**状態 (2026-05-30 案A 実装完了, Go受領済)**:
- `scripts/_gen-author-set-merges.py` → `data/seeds/series-merge-auto.json` (9,967 group)。
- `_promote-bulk-v2.py` の `load_merge_sids` を auto(JSON)+hand(YAML) 両 load に改修、 **同 sid は hand 優先**(うる星カラー版/SLF の手動キュレーション保護)。 JSON 採用理由=1万 group の PyYAML は数十秒。 edition-type 統合は hand のみ。
- 検証(find_related 直接、 SEED3 load 回避): 影響11ページで誤吸収ゼロ。 本番42ページ再生成で **実質変化2件のみ** = 半妖の夜叉姫 7→9巻(後期巻吸収) / アオアシ vol34 が重複standardレコードの dedup で別ISBN(要確認)。 SLF・うる星カラー版・他は不変。
- commit: 9cac0a1(機構) + edf6da7(本番再生成)。 種2 sqlite 不変・種3 不変・series_key 不変・可逆。

**STEP1+2 実装済 (2026-05-30, commit a11f9b1)**:
- **STEP1 再生成高速化** (10分超→warm 36秒): `_promote-bulk-v2.py` の load_seed3 を CSafeLoader + pickle cache (`.cache/seed3-promote.pkl`, mtime連動)、 build_parent_map も pickle cache (`.cache/parent-map.pkl`, DB mtime連動)、 `--only <slug>` でターゲット再生成。 full regen diff で perf改修の出力退行ゼロ検証済。
- **STEP2 取込もれ自動検出**: `_audit-volume-gaps.py` が `series-merge-auto.json` も load (案A統合反映)。 `--by-title` で gap検出 → 内部gap 7,214 / 高信頼単一欠け 1,859 (`.cache/seed4-candidates.csv`)。 半妖はvol8補完でgap消滅を確認。
- **半妖の夜叉姫 = vol1-10完成** (案A統合 sid126415+129242 + 種4 vol8 ISBN9784098537563)。

**A改善 = merge gating 緩和 (2026-05-30, commit 06de835)**: unmerged 352件調査で「著者集合完全一致」が厳しすぎと判明 → 緩和:
- 非人物トークン(社/プロ/スタジオ/編集=出版社imprint)を著者集合から除外(ホーム社混入で割れた GANTZ 等を統合)
- title正規化を audit の clean()(Unicode P/Z除去+lower)に統一(JOKER↔Joker 等)
- 著者集合「完全一致」→「包含(subset)で union-find連結」(原作/作画片欠け=入れ子を統合)
- over-merge ガード3層: 共通著者の積が非空 / アンソロジー題除外 / primary qid≤3
- 結果 9,967→**16,558 group**。 full promote dry-run で本番42ページ変化0(退行ゼロ)、 新規7,344 spot-check 全て正当、 三国志(別作者)は別group維持。
- **A1 partial-overlap回収 (commit 2559d25, 17,434→17,686)**: 役割忠実化後、 連結条件に「作画/単独著者(primary=artist/writer_artist)共有」を追加。 「原作のみ共通」(別作画の別adaptation: 小公女/椿姫/IS/マギレコ)は primary非共有で弾く、 同一作品の記録ムラ(春日局等)だけ統合。 qid4+ 0・本番変化0。 ※A2(改題)= 種2両側マッチ改題は既存kaitai-chain 9-12件で打ち止め(MADB改題note 286の大半は原版が種2に無い古書)= 安全な伸びしろ無し。
- **kana軸強化 (commit ceaef2d, 16,558→17,434)**: 種4登録で「種2に別クラスタで実在(表記揺れ)」29件発覚 → merge正規化強化。 clean()に括弧内subtitle除去+記号S除去、 **title_kana を第2キー**にローマ字↔カナ橋渡し(SHOGUN↔ショーグン/AZUMI↔あずみ)。 global union-find(title or kana共有+著者包含)。 ★続編/外伝ガード(component内でACT番号/異聞/外伝/第N編/Ⅱ食い違えば保留=DEAR BOYS↔ACTⅡ別ページ)。 qid3+14維持・本番変化0・29中8回収(残21はkana欠損/改題でvolumes-pending継続)。

**残 follow-up (改善ロードマップ STEP3-6)**:
- STEP3 **完了 (commit 5dad3ed)**: 候補 1,859 を DB自己照合で absent 1,507 / unmerged 352 に分類 → absent を NDL Search で ISBN裏取り(resumable batch、 hit 892/miss 615)→ 全892を validate(bind/重複OK、 ISBN-10→13)して **`data/seeds/volumes-supplement-auto.yml`(種4 auto、 source:ndl-auto)** に登録。 promote/audit を `volumes-supplement.yml` + `-auto.yml` 両 load に改修。 未確認 615 は **`data/seeds/volumes-pending.yml`** に追跡(将来 NDL更新/別ソースで再訪)。 audit gap 7,214→5,715。 ツール: `_seed4-candidates.py`(分類+NDL, resumable) / `_register-seed4-ndl.py`(登録)。 ★db再build/NDL再取得時は再実行。
- STEP4: 末尾取込もれ (最新刊がMADB未収録) を 種3/Wikidata総巻数と突合で検出 (内部gap検出の盲点)。
- STEP5 **実装済 (2026-06-01)**: 重複巻dedup tie-break を決定化。 同番号の重複ISBN(通常版+特装版が同日・同label「通常版」でMADB区別不可)で最古日が同じ時、 採用が行順依存=非決定的だった(12,015巻に重複/★1,085巻が非決定=edition内824+跨ぎ245)。 `get_editions_with_volumes` の dedup 2箇所に `_dedup_key=(最古release_date → 支配ISBN線[series内prefix[:9]頻度最多=通常版の可能性高] → 最小ISBN)` 導入で完全決定化。 日付区別可能な10,930巻は挙動不変(アオアシvol34=ビッグ採用で回帰なし)。 本番42のうち6ページ8巻が変化(urusei null→実ISBN/inuyasha元祖サンデー線等)し確認後デプロイ済(commit 510e513)。 ★残: 通常/特装の意味的判別はMADB fieldで不可能=Amazon API/価格データ待ち。
- STEP6: 案B = 安定work-id (ndla著者集合+正規化titleのhash) でクラスタキー化 → series-merge-auto.json の毎build再生成依存を撤廃。
- **STEP6 実装済 (commit 6970b95)**: merge を **series_key 参照(merge_keys)**に移行 = sid非依存。 series_key は166,441件すべて sid と1:1・ユニーク。 series-merge-auto.json(17,686)+ hand series-merge.yml + 消費側(promote/audit の load_merge_sids/edition_types に con引き回し + _entry_sids で merge_keys→現sid解決、 legacy merge_sids後方互換)。 本番42ページ変化0で挙動不変検証済。 → **db再build(sid変化)しても既存mergeが壊れない**。 種4は既にseries_keys、 役割は再導出可 → ⚠️再build連鎖の本体が解消(残: 新規work反映のため merge-auto/role/種4 の再実行は推奨だが、 既存は壊れない)。 ※probe/sim系(_sim-cluster/_audit-gap-summary等)はまだ merge_sids 読みでhand2件を見落とすが診断用で本番非影響。
- 保留56 group arc境界 = ユーザ裁定待ち。

**frag-merge 残清掃 (2026-06-01)**: 全DB dryrun(`_dryrun-fulldb-report.py` = read-only、 公開71,389ページ)で公開層の残分裂を精査。 ★素朴な「著者1人でも共有」のunion-findは**ハブ著者(監修山本博文/原作内田康夫/常連高原けんじ)経由で別作品を誤連結**(日本の歴史24作品が1群に)。 3段ガードで安全化: ①著者集合**完全一致**(交差でなく) ②**無副題のみ**(番外編/外伝=スピンオフ別ページ除外20件) ③merge_keysは関係auto群**全keyをunion**(上書き式load_merge_sidsのorphan防止)。 結果**43クラスタ/46ページ**(エヴァ3版/しゅごキャラ/石ノ森マンガ日本の歴史等の版違い)を`series-merge.yml`に純粋追加→公開71,389→71,343を実測。 ★公開層の真の版違い分裂は46ページ(0.06%)のみ=auto-mergeは既に機能。 残る同名異作1,345題(Akira/ガンダム)はtask2(副題/著者で表示区別)領域。 ツール: `_merge-frag-build.py`(提案+検証) / `_merge-frag-apply.py`(適用)。

**slug衝突からの再検証 (2026-05-31)**: slug生成器が当初 **merge を無視して種3 entry単位**で slug化 → はたらく魔王さま本編(029作画/和ケ原原作/qid の3断片、 merge-autoでは正しく1 group)を誤って3 slug+suffix化していた。 修正: `_slug-assemble.py` を merge-auto.json の代表key(巻数最大)でページ集約=1ページ1slug(commit 0c6e004)。 ★種3単位の分裂数(初測20,770)は過大、 **merge後の真の残衝突=1,950 base/4,924ページ**。 `_slug-collision-triage.py`(mangaka.csv で著者canonical化=武論尊↔史村翔↔qid)で三分類: **merge漏れ(著者共有)340 / 真の別作品1,610 / 判定不能0**。 merge漏れ340の大半は**翻訳版(鉄腕アトム韓国語/ASTRO BOY=意図的別ページ)+アンソロジー(on BLUE誌)**で正当 → **真の表記揺れmerge漏れは100-200程度**(accel-world: あくちぇる・わーるど。↔アクセル・ワールド=同著者HIMA / エヴァ日本版+NEON GENESIS英版)。 = 既存merge機構はほぼ正しく機能、 残りは kana軸/union-find への小追加で回収可能。 教訓: **slug等の派生物は必ず merge(series-merge-auto.json)適用後のページ単位で**。
