---
name: ousama_shitateya_4part_split
description: 【型・是正済】王様の仕立て屋=1頁に4部+傑作選が同居していた。巻抜け仮想が入口。頁分割の手順一式(stub+canonical+overrides+status/magazine-corrections)とsubtitle override新設
metadata: 
  node_type: memory
  type: project
  originSessionId: 732ebafe-0cf0-4d76-96d4-8692ce4b06b2
  modified: 2026-09-02T16:25:56.920Z
---

**2026-09-03 是正済**。巻抜け仮想の `standard:[17]` / `shinsoban:[14,15,16]` を追ったら、巻抜けではなく**1頁に4部作+傑作選が同居**していた。正史=NDL書誌77行(ユーザ提供TSV)+ja.wikipedia。

## 結果(巻は1冊も足していない=配置換えのみ。71冊 = NDL 75 − 傑作選4)
| 頁 | 中身 |
|---|---|
| `ou-sama-no-shitateya` | 第1部サルト・フィニート 全32巻(2004-01〜2011-11 JCデラックス/スーパージャンプ) |
| `ou-sama-no-shitateya-sartoria-napoletana`(新) | 第2部サルトリア・ナポレターナ 全13巻(2012-2016) |
| `ou-sama-no-shitateya-fiori-di-jirasoore` | 第3部フィオリ 全7巻(6・7巻を回収。**5巻で「完結」表示だった**) |
| `ou-sama-no-shitateya-shitamachi-tailor`(新) | 第4部下町テーラー 全19巻(17巻を回収) |
| drop | the special edition 4冊 = 傑作選集(既刊再収録)→ volume-exclude |

## 真因(2層)
1. 種2のクラスタキーの著者が**作画の大河原遁でなく原案協力・監修の「片瀬平太」**で、しかも表記ゆれで5分裂: `sub:下町テーラー` vs **`sub:下町テーラー.`(末尾ピリオド)**、`name:片瀬平太協力・監修`、`qid:Q11437087` [[series_fragmentation_rootcause]]
2. 2026-08-17の**ギャラ型一括是正がその壊れた区切りを edition-canonical に焼き込んで固定**していた [[gyara_type_regression_cleanup_state]]

## ★頁分割の手順一式(PoJ式。再利用可)
1. `data/manga/<slug>.yml` に stub(slug/title/wikidata_qid/`_skey`/title_romaji のみ)。**_skeyは親頁と同じでよい**
2. `data/seeds/edition-canonical/<slug>.yml`(★**suppress_types に既存typeを全列挙**しないと旧タブが残る)
3. `edition-overrides.json`: title/title_kana/title_romaji/year_started/year_ended/**anilist: false**
4. `status-corrections.yml`(completed) / `magazine-corrections.yml`(掲載誌)
5. ★**新slugは canonicalゲートが「死にキー」で止める**(manga.v2未生成のため)。先に `_promote-bulk-v2.py --only <slugs>` を1回流してから `_reflect-targeted.py`
6. ★**SRC stubは gitignore なので `git add -f`**(再生成不可。data/manga の force-track は8件の先例あり)

## ★promote に subtitle override を新設(2026-09-03)
副題は種3curate/種2代表行由来のため、**頁分割すると別の部の副題が残る**(第1部の頁に第2部「サルトリア・ナポレターナ」が出ていた)。`edition-overrides` の `subtitle` / `subtitle_kana` で上書き、**空文字=消す**(題名側に部名を含める頁=フィオリ式で二重表示になるため)。

## ★型として広げるか=検算した結論「広げない」
`series_key` の末尾記号だけが違う分裂を全DB掃引 → **1,436群**。ただし**1,187群は同じ本番頁に着地=無害**、別頁に割れているのは**1件のみ**(鎌倉ものがたり/魔界編=正当)、248群は本番未掲載。**王様が特殊だったのは、sub側キーにqidが無く、かつ1題に4作品が入っていたから**。生の件数で型宣言せず検算すること [[feedback_sanity_check_tool_warnings]] [[feedback_one_bug_means_a_class]]
