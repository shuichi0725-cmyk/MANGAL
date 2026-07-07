---
name: tinyfish-web-fetch
description: TinyFish=APIの無い/標準WebFetchが弾かれるサイト(潮出版社usio.co.jp等)の取得手段。scripts/_tinyfish.py・キーは.env
metadata: 
  node_type: memory
  type: reference
  originSessionId: a2ed548f-4b21-42ea-9ad0-229054bf2d45
---

**TinyFish** = AIエージェント向けWebインフラ。MANGALでは**NDL/楽天APIに無く標準WebFetchが返らないサイトの取得**に使う(2026-07-08導入)。

- **ツール**: `python scripts/_tinyfish.py fetch <URL>...`(ページ→Markdown・最大10URL・POST) / `search "<クエリ>"`(Web検索・★GET・レスポンス{query,results:[{title,url,snippet}],total_results})。コード内 `from _tinyfish import fetch, search`。urllib実装(requests不要)。★Search=GET(POSTは失敗する・2026-07-08修正)。
- **キー**: `.env` の `TINYFISH_API_KEY`(★git追跡外=絶対コミットしない)。
- **料金**: Fetch/Searchは**無料枠**(150URL/分)。Agent(フォーム操作)/Browser(ステルス)のみクレジット消費=MANGALではほぼ不要。
- **実証**: Fetch=usio.co.jp(潮出版社)取得成功。Search=スゴ盛が実話系4コマ雑誌(Wikipedia+版元ドットコム)と確定=「これはアンソロ/雑誌か」の性質判定に強い。
- **使いどころ**: 出版社公式(潮/小さい版元)・電書ストア(cmoa/BookWalker JS重)・Amazon書影/在庫など「APIが無い＋WebFetchが弾かれる」時。**主力は今まで通りNDL(_lookup.py)+楽天**で、それで埋まらない時だけTinyFish。[[external_data_access]]の補完。
- 位置づけ=**必須でない便利ツール**(ユーザ評)。per-case/蒸留で「公式にしか無い版情報」を取る時に想起する。
