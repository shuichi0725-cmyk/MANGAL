# 成人判定の2フラグ + geo出し分け 設計(2026-05-31)

## 背景・決定
アフィリエイトの最終目標は日本 → 米 → 他国の Amazon Associates。 成人判定の基準が
**日本(成年マーク)< 米(explicit全般)** で、 どちらか一方では片方の市場に不適。
→ ★**訪問者の国で出し分ける**(Cloudflare geo)= 収益とコンプラの両取り。

## 核心の気づき(実装が小さい理由)
現本番(`_promote-bulk-v2.py`)は **`adult_score < 3` のみ採用** = **日本基準で18禁を既に除外済**。
- ∴ **adult_jp 作品はもう本番に居ない**(変更不要)。
- 残る課題 = **「日本では全年齢(=本番に居る)だが、 米基準では adult」**な作品
  (回復術士のやり直し / 終末のハーレム / うみべの女の子 / ノゾキアナ 等 ≒ 青年誌explicit)。
- → これらに **`adult_us` フラグを付与**するだけ。 種2/ingest は不変。

## フラグ定義(各本番ページ)
| フラグ | 定義 | 用途 |
|---|---|---|
| (adult_jp) | adult_score>=3 = 既に本番除外 | 出力不要(本番=全て日本OK) |
| **adult_us** | 種a(v14マッチ)`isAdult=true` | 非日本アクセスで非表示 |

- `adult_us` = マッチ済 種a が isAdult。 マッチ無し(~56%)は **false**(米signal無し=表示)。
  = 限界(未マッチの青年誌explicitは米に漏れうる)だが、 種aカバー分は正しく隠せる。
- マージページは構成 series_key の **OR**(1つでも米adultならページ adult_us)。

## 配信(Cloudflare、 後日・本dataの外)
```
CF-IPCountry == JP  → adult_us 無視(フル表示。 Amazon JP タグ)
CF-IPCountry != JP  → adult_us=true を非表示(Amazon US 等タグ)
```
※VPN等でgeo不完全だが geo-fence は業界標準。 Amazon の国別タグもこの前提。

## 実装ステップ(慎重・段階)
1. **adult_us マップ生成** `scripts/_build-adult-us-map.py` = match-v14 + dump isAdult →
   `{series_key: true}`。 出力 `.cache/adult-us-map.json`(再生成可)。
2. **promote 統合**: マップ load → 各ページの series_key(merge込)を OR → yml に
   `adult_us: true`(true の時のみ出力)。 種2/adult_score/採用ロジック不変。
3. **検証**: 42サンプル再生成で破壊0 + adult_us 件数 spot-check(回復術士等が true か)。
4. (将来)Cloudflare Worker で geo 出し分け + 国別アフィリエイトタグ。

## 不変条件(保護)
- 種2(db-v2)/ adult_score / ingest = **不変**
- 現本番の採用作品集合 = **不変**(adult_us は表示制御の付加情報、 除外を増やさない)
- adult_overrides.yml(17件)= そのまま有効
- 可逆(adult_us 出力を消せば元通り)
