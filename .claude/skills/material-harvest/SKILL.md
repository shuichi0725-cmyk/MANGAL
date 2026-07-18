---
name: material-harvest
description: 素材ハーベスト=本番に書かず「素材」だけ収集するアイドル柱(発売日精密化/エンリッチ素材/status証拠/infobox書誌/賞)。実行体=_material-harvest.py。Sonnet運転前提
---

# 素材ハーベスト (= 2026-07-17 新設。アイドル運転の柱)

**収集と生成の分離**が原則: この skill は素材を貯めるだけで、**本番頁には一切書かない**。
生成/反映は各既存 protocol が担う(catch/synopsis=skill enrich-catch-synopsis / status=skill completion-judge / 反映=各ゲート)。

## トリガー語
- 「**素材ハーベストして**」= 下の運転順を回す(アイドル運転の柱としても呼ばれる=skill idle-run)
- 「素材ハーベスト <フェーズ名>」= 特定フェーズのみ

## 運転順 (= python scripts/_material-harvest.py <cmd>)

| # | cmd | 何を | コスト | 頻度 |
|---|---|---|---|---|
| 1 | `triage` | worklist再構築(日付粗い巻/enrich欠落/QID) | ローカルのみ・数分 | 週1 or 大変更後 |
| 2 | `dates-local` | 楽天cache→発売日精密化候補をseedへ | ローカルのみ・数分 | cache更新後 |
| 3 | `wiki-link` | 作品QID→jawiki記事名(QLever一括) | 外部・数分 | triage後 |
| 4 | `wiki-fetch --limit 500` | 記事wikitext取得+infobox抽出 | 0.8s/req=★長丁場 | アイドルの主食 |
| 5 | `awards` | 作者+作品QIDのP166受賞(QLever) | 外部・数分 | 月1 |
| 6 | `fish-residue --limit 50` | wiki無し×caption無し残差を魚 | 魚無料枠 | アイドル |

- 全cmd**再開可能**(done-set/逐次追記)。「やめて」=プロセス停止でよい(次回は続きから)。
- ★**作品wikiの結線元 = `.cache/work-qid-map.json`(anilist_idキー・P8731由来・qid有5,754)**。
  頁の `wikidata_qid` は**作者QID名前空間**(2026-07-17実測=44k頁全て作者QID)なので作品結線に使うな。
  作者QID→jawiki記事は `author-wiki-links.jsonl`(5,664件・作者素材として有効)。
- 初回実績(2026-07-17): 日付候補98,642 / 月ズレhold35,911 / wiki記事結線3,478(在庫≒46分) /
  賞=作者196人・作品68作(高橋留美子=アイズナー殿堂・大友=アングレームGP等の海外賞込み)。
- ★fish-residue は **`.env` の TINYFISH_API_KEY が必要**(新PC移行で欠落しうる=穴④の教訓)。

## 収集物と置き場

| 素材 | 置き場 | 下流(誰が使うか) |
|---|---|---|
| 発売日精密化候補 | `data/seeds/release-date-fill.jsonl` | ★**promote結線済**(2026-07-18 GO消化。書影と同じ最終passでprefix精密化のみ充填=`_date_fill_for`) |
| 日付矛盾hold | `.cache/enrich-material/dates-conflict-holds.tsv` | 奥付月vs実売月の月ズレ型が主。裁定マター |
| wiki本文(raw) | `.cache/enrich-material/wiki/<slug>.wiki.txt` | enrich素材・status証拠の原本 |
| infobox抽出 | `.cache/enrich-material/wiki-extract.jsonl` | 掲載誌/連載期間/巻数/受賞/hiatus_mention |
| 賞(作者/作品) | `.cache/enrich-material/awards-{authors,works}.jsonl` | 作品awards結線・著者受賞(表示は著者ページ構想待ち) |
| 魚素材 | `.cache/enrich-material/fish-material.jsonl` | enrich素材(残差) |
| 魚サイト台帳 | `.cache/enrich-material/fish-site-ledger.json` | ドメイン別 ok/blocked(無料枠で見えるサイトの簿記) |

## 鉄則

- **本番(manga.v2/preview/種1-4)に書かない**。書くのは素材庫と `release-date-fill.jsonl`(未結線seed)のみ。
- 日付は**精密化only**(空 or prefix一致だけ候補化。矛盾=hold。上書き訂正はこのジョブでは絶対しない)。
- 収集した紹介文は**素材**(公開文への逐語コピー禁止=synopsis運用どおりAI要約・言い換え)。
- 魚は fetch/search 無料のみ(Agent/Browser=有料=要ユーザ承認)。量より**サイト種別**が制約=台帳に簿記。
- Amazonは対象外(PA-APIのみ合法の既裁定)。
- 429/5連続エラー=即中断(再実行で再開)。NDL/楽天liveは使わない(このskillはwiki/QLever/魚/ローカルのみ)。
- Sonnet運転時: **判断はscript・AIは運転と保留裁定のみ**(創作的判断をしない)。

## GO待ち(結線マター=ユーザ裁定)

1. ~~release-date-fill.jsonl → promote結線~~ ★**済(2026-07-18)**: フルpromoteで98,703巻精密化・矛盾skip20。dates-local再収集後は次のpromoteで自動反映
2. **日付月ズレhold**(~3.6万件)の扱い(奥付月→実売日への訂正は精密化でなく上書き=別ルール要)
3. **hiatus付与基準**(schema/表示は実装済・7頁使用中。機械証拠でどこまで広げるかの線引き)
4. **作品awards結線**+賞名マスター(closed vocabulary)・著者受賞歴の置き場/表示

## 報告形式
- フェーズごとに「+N件(累計M) / hold K / 中断理由」。魚は「取得N/失敗M/台帳更新」。

## 関連
- 運転の親=skill idle-run / 生成=skill enrich-catch-synopsis / status=skill completion-judge / 魚=skill tinyfish
