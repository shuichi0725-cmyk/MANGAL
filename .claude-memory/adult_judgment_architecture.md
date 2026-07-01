---
name: adult-judgment-architecture
description: 成人判定(18禁)の機構と Phase A 誤爆潰し。基準=日本MADB成年、レーベル有効、作者signalが誤爆源、override機構で17件un-flag
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

MANGAL の成人判定(調査 2026-05-31、 詳細 `docs/adult-judgment-crosscheck.md`)。

**基準 = 日本の18禁(成年コミックマーク)。** 種a(AniList)isAdult は米基準でBL/TL/ecchiを広く拾う(日✗米◯=2,158)ので**参考のみ**。 日◯米✗はわずか3=MADB成年⊂AniList。

**判定の所在**: 種2 `series.adult_score`(取込時 fetch-madb.ts で計算)。 **promote が `adult_score < 3` のみ本番採用**(>=3=adult除外、 6,739件)。 ★種3 schemaに adult field 無し=種2層。 ★成人判定は**本(巻)単位**(MADB raw `schema:contentRating="成年コミック"`=8,179冊/per-ISBN)だが series.adult_score にシリーズ集約され粒度ロス(混在23件)。

**signal(adult_signals)と精度**(6,739除外の内訳):
- `madb_content_rating`(weight5)=4,935(73%)= ★権威・漏れ0。
- `adult_imprint`/`adult_publisher_imprint`(w3)=1,300 = adult出版社レーベル、 **正当な捕捉**(成年マーク外のTL/官能も種aタグ上90%成人向け)。 ★ユーザの「レーベル判断が有効」は正解。 adult_publishers(21)/imprints(235)に**講談社等の一般大手誤混入は無し**。
- `wikipedia_adult_mangaka_list`(作者)=★**誤爆源**(作者がadultも描く→全年齢作品まで誤判定)。 但し作者only 504件のうち**95%は本物adult**、 真FPは~24件のみ。「講談社誤爆」の正体はこの作者signal(出版社リストでない)。

**Phase A 修正(surgical、 大改造不要)= override機構**:
- `data/seeds/adult-overrides.yml`(新seed・純粋追加)= force非adultの series_key。 `_promote-bulk-v2.py` の `_load_adult_overrides()` が読み adult_score>=3でも本番採用。 種2不変・再build耐性・可逆。
- **17件確定**: 種a全年齢確認12 + 楽天確認3(理想のヒモ生活等)+ 手動2(コープスパーティー/艦これアンソロジー)。 残~19は楽天未収録/不明/成人寄り題で**保守的に維持**(成人漏れ回避)。

**ISBN裏取りインフラ(再利用可)**:
- `.github/workflows/validate-adult-isbn.yml`(GitHub Actions、 既存 RAKUTEN secret 流用、 workflow_dispatch)= ユーザが Androidから Run可。 → verdict を repo に commit-back。
- `scripts/_validate-adult-isbn.py`(楽天 BooksBook + Google Books、 2026仕様: openapi.rakuten.co.jp / accessKey param / Referer-Origin header / availability=0)。
- ★楽天Books は**成人フラグ無し + 一般API非収録** → 「一般カタログ在=全年齢」判定。 在庫制限で絶版/ニッチは notfound(検証不可)。
- ★Rakuten/Google/Amazon キーは **GitHub Secrets**(ローカル.env無し)。 fetch系は全部 Actions 実行(Android開発由来)。 Amazon PA-API は未設定=フェーズB(最終目的=アフィリエイト)。

**★2フラグ + geo出し分け(2026-05-31 設計+実装、 commit 5aebd53、 docs/adult-geo-two-flag-design.md)**: ユーザ判断=日本基準(成年マーク)< 米基準(explicit全般)で、 どちらか一方では片方の市場(Amazon Associates 日/米)に不適 → **訪問者の国で出し分け**(Cloudflare geo)が最適解。
- ★核心: 現本番は既に日本基準で18禁除外済(adult_jp は本番に居ない)。 残る課題=「**日本OKだが米adult**」(回復術士のやり直し/うみべの女の子/終末のハーレム/ノゾキアナ ≒ 青年誌explicit、 成年マーク無いが内容adult)。 → これに `adult_us` フラグを付与するだけ(種2/ingest/採用集合**不変**=表示制御の付加のみ)。
- **adult_us = 種a(v14マッチ)isAdult**(米基準)。 `_build-adult-us-map.py`→`.cache/adult-us-map.json`(2,709 series_key)。 `_promote-bulk-v2.py` が load し各ページの series_key(merge込)OR で `adult_us: true` を yml 出力。 本番採用×adult_us=**約1,911件**(非日本geoで非表示対象)。
- union実測(`_audit-adult-union-proto.py`): 種a追加で新規adult化1,913(Hentai491/Ecchi356/百合83/その他983)。 高pop=本物explicit(うみべ/回復術士/終末のハーレム=米Amazonリスク層)。 遊人6作(校内写生等)も救済。
- 配信(Cloudflare Worker geo: CF-IPCountry==JP→adult_us無視/≠JP→非表示 + 国別Amazonタグ)= 後日。 VPNで不完全だがgeo-fenceは業界標準。
- ★【確認 2026-06-22】geo配信は**依然未実装**。`worker.js`=8行の静的アセット素通し(env.ASSETS.fetch)のみ・国判定なし。`adult_us`は promote が計算してdetail ymlに出すが**UI/lib/Workerのどこからも参照されてない=消費者ゼロ**=現状海外からも全作見える。adult_usフラグは「準備OK・配信ゲート未実装」。実装する場合=worker.js拡張(request.cf.country+adult_us slug一覧でブロック) or geo別索引2系統。※軽量化でadult_usは「未使用だが将来geo必須」につき**消さず保持**。
- ★遊人/ANGELの最難ケース: ANGEL=シュベール出版版が18禁/一般版は非18禁=**版(edition)単位**でしか正しくない。 MADBはシュベール版も成年指定漏れ(成年ISBN=0)。 種aは校内写生(Hentai)を捕捉するがANGEL(Ecchi)は非adult=一般版と整合。 edition単位adult列が本筋の宿題。
- ★adult_us map は match-v14 依存(matcher v9→v14、 [[anilist_matching_state]])。 match更新時に再生成要(intake未統合)。

**残改善余地**: edition単位adult列(遊人/ANGELのシュベール版)/ 種a未マッチ56%の米基準漏れ / 作者signal corroboration / Amazon成年node(PA-API設定後)。 関連 [[anilist_matching_state]] [[openbd_eol_amazon_required]]。

## ★【決定済 2026-06-13】adult判定v3 = 楽天収穫完走後に新規構築(ユーザ「1」選択)
- ★トリガー: 楽天収穫(.cache/rakuten-isbn.jsonl、目標182,357)完走後に着手。
## ★【設計原則・2026-06-13 ユーザ指摘】成年holdは「積極証拠」で。「楽天不在」は単独判定にしない
- ★**楽天不在の正体は成年と『新しすぎ』が区別つかない**。ブランニュー非成年漫画はまだ楽天未掲載 → 「不在=成年hold」だと**出すべき新刊を握り潰す**(=今夜の漏れ[過少hold]の鏡像=過剰hold)。
- ★**解=hold判定は陽性証拠のみ**: MADB成年フラグ ∨ dbsearch成年作家([[adult_signal_dbsearch]]) ∨ 成年imprint一致(新旧非依存)。**楽天不在は「調べろ」フラグで、重みは 古さ×複数巻 で上がる**(不在+複数巻+発売半年=強/不在+新刊=弱=たぶん新しすぎ)。これで漏れ(陽性が捕まえる)と新刊潰し(不在単独で握らない)を同時防止。
- ★**マニフェスト/ゲートに非掲載理由を型で記録**([[intake_manifest_gate_design]]): `adult確定`(握る)/`不確実=楽天不在だが陽性なし&新しい`(=新しすぎ濃厚→最低状態で出す or 暫定掲載、次蒸留で楽天追いつき再判定)/`未取込`/`最低掲載vs完備`。**掲載鮮度と成年確実性を切り離す**=非成年は早く出し、握るのは陽性確定成年だけ。
- ★MADB更新が遅すぎ(月次+登録ラグ)→ 鮮度主源を NDL+楽天+サイトCSV予約 に移し、MADBは backfill/訂正回収/成年corroboration に降格(ユーザ方針 2026-06-13)。

- ★具体的に追加すべき成年imprint(2026-06-13 ユーザcm101データで発見): **IDコミックス Lake / Rex c**(一迅社サブレーベル。「下剋上セックス」「ヤンデレご主人様の甘い支配」等の成年なのに adult-imprints.yml 未収載)。サブレーベル粒度の穴=v3で塞ぐ。
- 設計方針 = 多シグナル合議: ①レーベルリスト(維持) ②★**楽天ブックス不在×複数巻**(最強新シグナル、楽天は成年を扱わない・no_hit僅少0.7%、リスト保守不要で新レーベルにも自動で効く) ③★**作者伝播**(その作者の他作品成年率。板場広し型=名義使い分けも捕捉) ④掲載誌レイヤー(成年誌=ほぼ確定、未使用) ⑤可能なら版(edition)単位スコア。
- ★正解セットで実測: 今回の漏えい2,233件+MADB成年確定をvalidationにして precision/recall を測ってから閾値決定(v2は無測定だった)。
- 位置づけ = 成年3分けレビューUI([[adult_triage_review_pending]])に渡す候補を絞る前段。
- ★同時候補(ユーザ発案・価値あり判定済): **種1全量スイープ監査** = cm101全record−(本番+成年hold+drop理由付き)の「説明なし残渣」を機械抽出 → 残渣にv3判定をかけ、非成年=「乗せるべき漏れ」候補に。動機=作者名表記揺れ/作者リスト外の作者で取りこぼしの疑い([[author_data_map]]の表記揺れ問題と同根)。月次流入カバー65-70%([[monthly_intake_reality]])のギャップの正体特定にもなる。第一歩=簿記監査(全ISBNに排除理由を付ける)だけならAIコストほぼゼロ。
