---
name: search_404_build_skip_validation
description: 検索に出るのに404=索引(Python検証なし)とNextビルド(Zod検証あり)の不整合。検証エラーのページはbuild skip→404。全角数字日付/master外genreが典型
metadata: 
  node_type: memory
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

2026-06-29 ユーザ発見「フォルダ名変わって検索からいけなくなってない？」の調査結論。

**機構**: ★`_build-list-index.py`(Python)は**検証なし**でymlを索引化するが、`lib/loadData.ts`の`loadAllManga`は**Zod(MangaSchema)+publisher/genre/magazineキー検証**し、不良ページを**try/catchでskip**(233-262行)→`generateStaticParams`がそのslugを生成しない→**検索索引には載るが/manga/[slug]は404**。確認=`curl -o/dev/null -w%{http_code} https://mangal-preview.pages.dev/manga/<slug>` / ローカルは`MANGAL_DATA_DIR=.preview-data` + loadAllManga の skip警告。

**典型原因2つ(実際に踏んだ)**:
1. ★**全角数字**: NDL由来の日付`１９８２`(`１..`)。Python `\d`は全角を拾い release_date に入れるが、schema `release_date: ^\d{4}(-\d{2}(-\d{2})?)?$` はASCIIのみ→reject。**NDL等の外部値は`unicodedata.normalize("NFKC", x)`必須**(生成器修正済)。日付正規表現も`[0-9]`明示が安全。
2. ★**master外genre**: `genre 'other'`(data/genres.yml 32キー外)→loadData line252で「未定義genre」throw→skip。除去すると今度は`genres min(1)`違反→**schemaを`genres: z.array().default([])`に変更**(空許容)。ユーザ方針[[ai_genre_closed_vocabulary]]「該当無ければ空でよい(other行きより未付与)」準拠。適当にジャンルを当てない。

**教訓**: ★索引化と本番ビルドで**検証粒度を揃える**。新データ生成後は `loadAllManga` の skip 0 を確認してから索引化・push。slug変更でなくvalidation skipが「検索404」の正体だった。[[preview_deploy_pitfalls]] [[edu_multiedition_disentangle_ndl]]


## 2026-07-01 追記: release_date不正形式が最大の404源
- Zod: release_date は正規表現 4桁年(-2桁月(-2桁日)?)? 形式が必須。**NDL生形式(2014.8 / 1997-9 / 全角２００５．４)は落ちる**。種4巻補完でNDL日付を未正規化で入れて153件混入→70頁が404だった。
- ★恒久策: **promote clean_vol に `_norm_date` 統合済**(NFKC正規化 + ドット/スラッシュを ハイフンへ + 月を2桁ゼロ埋め)。種4 seedも正規化済。今後の日付入りseedは自動正規化される。
- ★preview同期の罠: **内部slug≠ファイル名(slug-override頁)を、ファイル名一致で同期すると消える**。preview欠落23作はこれ(slug-aliasesで逆引き回収)。同期は内部slug基準で。
- 検証法: `.preview-data/manga/*.yml` の release_date が全て YYYY-MM形式か + 検索索引slug==頁内部slug を確認(不整合0が正)。

## 2026-11-26 追記: 頁skip+週次prune=公開中の頁が本番から消える
- ガラスの城2巻の発売日「１９９１」(全角)でビルド検証が頁ごとskip→`--prune` 同期で本番から削除→finalize の索引⊆生成頁で初めて止まった(同期の後=手遅れ)。部分ビルドで戻した。
- ★恒久策3点: ①`_weekly-postbuild.py` に索引⊆生成頁ゲート(**同期の前**・--no-gate でも止める)②promote 最終pass で release_date を `_norm_date`(clean_vol を通らない経路があった)③`_check-edition-canonical.py` が半角 YYYY[-MM[-DD]] 以外を異常に。
- ★Python の `\d` は全角数字にも当たる = 日付の形式検査は `[0-9]` で書く。
