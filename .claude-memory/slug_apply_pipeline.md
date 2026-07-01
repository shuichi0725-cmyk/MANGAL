---
name: slug-apply-pipeline
description: "【完了+運用手順】slug適用の正しい実行順序と罠(2026-06-11本番適用済・69,004ページ)。残=Stage E(ISBN振り直し920)とStage F(版クラスタ統合スイープ)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★2026-06-11 slug新規則を本番適用完了(69,004ページ・slug一意・alias 30,533)。

## 正しい実行順序(再適用・蒸留後はこの順)
1. `_slug-gen-v1.py` → `_slug-gen-v2.py` → `_build-slug-override.py` → `_slug-assemble.py`
2. `_rekey-slug-assets.py <直前世代のslug-final backup>`(c2/recluster/volume-finalのbase繋ぎ直し)
3. `_slug-collision-triage.py` → `_gap-c1-suffix.py` → `_gap-c2-slug.py`
4. `_integrate-slugs.py`(検証込み) → `_slug-apply-prep.py`(★成年ゲート内蔵=adult_score>=3をhold、2026-06-13配線) → `_slug-apply-build.py`
5. `_promote-bulk-v2.py`(~13分) → ★**`_slug-apply-recluster.py`(promote後必須**=recluster31ページはpromote非関知)
6. `_resolve-applytime-and-alias.py --alias` → `--hygiene`(alias生成+整合性)

## 今日踏んだ罠(再発防止)
- ★**c2のreps列は裁定時点に凍結**(rekeyで再導出すると規則改訂後の未裁定同居ページがmerge対象に混入=ドリフト)。rekey済列は保持される実装に修正済。
- ★**apply-prepはrep単位**(全key出しはmerge群同slugをapply-buildがcap衝突誤認→`-2`偽ページ4,500件)。
- ★**latin題はtitle優先**(AniList romaji誤マッチでONE PIECE本編が読切slugに=旧本番から存在した既存バグ)。kata題は音写ガード+★長さ条件(romajiが読みの1.5倍超=副題付き過剰マッチ: dragon-ball-episode-of-bardock型)。
- ★**kata-dict適用は3カナ以上+敬称ブラックリスト**(サン→sun/ジン→jing/ユウ→iu の和語衝突)。
- ★promoteは data/manga.v2 を再生成する=recluster生成・ISBN振り直しは毎回promote後に再実行が必要。
- alias hygiene = 英語名時代の遺物(kimetsu→demon-slayer等)が現役ページを乗っ取るのをSELF-DROPで防止。

## ✅ Stage E 完了(2026-06-11深夜) = ISBN振り直し配線
- `_apply-volume-moves.py`(promote+recluster後の後処理パス=★手順6.5として毎回実行): recluster ISBN(145)はrecluster優先でsupersede→673 ISBN移動/146ペア。★ページ生成11(魔法科6ライン+よんこま編+gakkou1994+TO HEART/To-y/夢で逢えたら=ソースclone方式でenrichメタ継承)/空ページ消滅25(魔法科混線旧8頁含む、aliasはstagee-aliases.tsv→slug-aliasesへ統合)。
- ★検証: **行き先に無い=0**。541=行き先正+他ページに残コピー(=D保留252群「現状維持」ユーザ決定済の残余)。34=v2に不存在(record drop済)。
- ★「位置不一致」は**恒常的に~314出る=正常**(2026-06-13確認): slug-volume-final.tsvの目標slug名が後段改名(ninku→ninkuu/comic-tulip等)・recluster裁定(shikakenin)・既知FLAG(こわい本/伯爵カイン)に追い越された陳腐化。実ページ題を確認済=巻の混入なし。急増した時だけ調査。
- ★page-dedup.ymlのstale罠: 旧slug基準のdrop指定が新世界の実ページを殺す(aa-megami-sama消失で発覚)→`_rekey-page-dedup.py`で572→367(197=merge済で廃止)。★slug改訂したらpage-dedupも必ず再キー。

## ✅ Stage F 完了(同日) = 版クラスタ統合24群
- `_edition-cluster-sweep.py`(版マーカー題/副題キー∧qid共有)+`_stagef-verify.py`(ISBN出版社帯+巻相補)で機械確証→24群merge(SLAM DUNK全版/DEAR BOYS新装[Web確証]/マンガ日本の歴史 単行本+中公文庫/ああっ女神さまっ 等)。
- fix行: slam-dunk / tokyo-ghoul(★:reが無印slugを占有していたのを解消→tokyo-ghoul-re) / linebarrels / さいとう・たかを=takao。DROP: ONE PIECE総集編×2(抜粋本protocol)。
- ★HOLD 3: SLAM DUNK編集部名義4冊(8342帯・全巻番号1=ムック疑い、要NDL) / 海の大陸NOA(plus絡み不明瞭) / 後ハッピーマニア(続編=別ページ正当)。

## 残(次回)
- 裁定なし衝突 ~210群(.cache/c2-unverdicted-new.tsv)のWeb裁定スイープ(機械suffixでURL安全=非ブロッカー)。
- 残コピー541(D保留252群)の将来解消 / 34不存在ISBNの棚卸し。
- 最終ページ数 68,803(漫画68,771+recluster31+Stage E純増-25消滅+11生成)。

## 2026-06-26 フリガナ基点slug修正787(slug-fix-834)
連結slug→ハイフン区切り(joukyoukoroshiyamusume→joukyou-koroshiya-musume)。`scripts/_apply-slug-fix-834.py`(候補=`data/seeds/slug-fix-candidates-2026.json` 834=`{old:new}`)。クリーン**787**のみ適用=衝突22(同名異作:赤いちょう/赤い蝶等=姓年suffix別途)・重複new0・上書き0・no-op25 を除外。durable=slug-overrides.yml(promoteの`_slug_override`が再promoteでも保持)/旧→新301=slug-aliases.yml+public/_redirects/rename=preview+manga.v2のyml+slug欄/可逆=changelog(.cache)。
- ★罠: slug-aliases.yml を `load+sorted+rewrite` すると**数値キーslug(純数字)で sorted int/str 混在TypeError**→`open(w)`がtruncate後にエラーで**ファイル空化事故**(29,619→0行)。`git checkout`で復元+changelog(.cache)の787を追記して回復。以後**追記モード('a')で書く**(sortしない)。
- ✅**衝突22完了**(2026-06-26): 新slugが既存別ページと衝突した22件を1件ずつ実データ精査(`_apply-collision-22.py`/裁定=`docs/collision-22-resolution.tsv`)。**suffix13**(同名異作→著者姓/年suffix 赤いちょう→-umezu)+**subtitle2**(サブシリーズ→副題slug 鎌倉ものがたり魔界編→-makai-hen)+**swap1**(主版逆転=新・幸せの時間21巻が無印,シン幸せ2巻→-2026)+**edge1**(incumbent誤slug退避=赤い髪の少年/クリスマス同ISBN)+**dedup5**(真の重複=ISBN包含確証incumbent⊂candidate→完全版採用+`page-dedup.yml` drop)。★dedup恒久化=page-dedupのskipは`src_yml[slug]`(override前)判定なので drop:incumbent生slug + override:candidate旧→clean が両立。**slug-fix-834全件(787+22)完了**。本番索引はR2デプロイ時に再生成。

関連: [[pending_slug_generator]][[multi_edition_unification_pending]][[collision_slug_investigation]][[madb_volume_misnumber_fix]][[acquire_all_obtainable_info]]
