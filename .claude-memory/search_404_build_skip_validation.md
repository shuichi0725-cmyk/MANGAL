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
