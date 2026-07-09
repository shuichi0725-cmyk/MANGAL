---
name: tinyfish
description: TinyFishで/タイニーフィッシュ=APIが無い+標準WebFetchが弾かれるサイトの取得(fetch)とWeb検索(search)。無料枠のみ・主力はNDL/楽天(_lookup.py)でそれで埋まらない時の補完
---

# TinyFish (= WebFetch補完。2026-07-08 導入・2026-07-10 skill化)

AIエージェント向けWebインフラ。MANGALでは **「APIが無い + 標準WebFetchが返らない/弾かれる」サイトの取得** と、
**性質判定のWeb検索**(これはアンソロか/雑誌か等)に使う。位置づけ=**必須でない便利ツール**(ユーザ評)。

## 使う順番 (= エスカレーション。いきなりTinyFishに行かない)

1. **NDL/楽天/キャッシュ** = `python scripts/_lookup.py`(skill external-data-access が正本)
2. **標準 WebFetch/WebSearch**(Wikipedia・大手サイトはこれで足りる)
3. **TinyFish** = 上2つで取れない時だけ(出版社公式=潮出版社usio.co.jp型・小さい版元・JS重の電書ストア=cmoa/BookWalker・Amazon書影/在庫)

## 使い方 (= scripts/_tinyfish.py。urllib実装・requests不要)

```
python scripts/_tinyfish.py fetch <URL> [<URL>...]   # ページ→Markdown本文(最大10URL/回・POST)
python scripts/_tinyfish.py search "<クエリ>"          # Web検索→構造化JSON(★GET。POSTは失敗する)
```
コード内: `from _tinyfish import fetch, search`
- `fetch(urls, live=True)` = キャッシュ無視(ttl=0)。既定はTinyFish側キャッシュ応答。
- `search(query, purpose=...)` = 応答 `{query, results:[{position,title,url,snippet,site_name,date?}], total_results}`。purposeで検索意図を補足できる(任意・2000字まで)。
- fetch応答には `results[]` と別に `errors[]`(url/error/status)が出る。エラーは黙って捨てない=件数を報告。

## 鉄則

- **キー = `.env` の `TINYFISH_API_KEY`**(git追跡外。★絶対コミットしない。無ければ即エラーで止まる)
- **無料枠のみ使う**: Fetch/Search=無料(150URL/分)。**Agent(フォーム操作)/Browser(ステルス)はクレジット消費=使う前に必ずユーザ承認**。e-hon等セッション必須の検索は無料Fetchでは不可=有料Browser領域。
- **一次ソースの序列は変えない**: 書誌の正はNDL/楽天。TinyFishで取った公式ページ情報は「NDL/楽天に無い版情報・発売情報の補完」であり、既存データを上書きする根拠には単独でしない(2ソース確証の原則はそのまま)。
- 大量fetch(数十URL超)は他のharvest同様、事前に件数予告+逐次追記+再開可能にする(skill long-job-ops)。

## 実証済みの型 (= どういう時に想起するか)

| 型 | 例 | 使うもの |
|---|---|---|
| 出版社公式にしか無い版/刊行情報 | 潮出版社 usio.co.jp(WebFetch不通を fetch で取得成功) | fetch |
| 「これはアンソロ/雑誌か」の性質判定 | スゴ盛=実話系4コマ雑誌と確定(Wikipedia+版元ドットコムがsnippetで出る) | search |
| per-case/蒸留で楽天・NDL両方に無い書誌 | 小版元の公式・電書ストア商品ページ | search→fetch |

## 報告形式
- fetch: 取得N/失敗M(errorsの内訳)。search: ヒット要旨+採用したURL。
- 取れなかった時は「無料Fetch不可(セッション必須)=有料Browser領域」かを区別して報告(ユーザ承認マター)。

## 関連
- 照会の正本=skill external-data-access(まず _lookup.py) / 事実の記録=memory [[tinyfish_web_fetch]]
