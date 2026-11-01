---
name: volgap-audit
description: 巻抜け仮想=残巻抜けを算出(~2分・promote不要)。単巻切り詰め検出(solo-truncated)もここ
---

# 巻抜け仮想 / 巻系監査

## 巻抜け仮想 (トリガー語: 「巻抜け仮想」)
```
python scripts/_volgap-virtual.py --list
```
本番DBの巻抜けフィルタを仮想再現(未promoteのseed適用後の残欠を~2分で算出)。促されたら件数+内訳(ISBN有無/homonym)を報告。
★方針: ISBN無し・homonym絡みは無理しない(skip)。安全fixのみ。per-caseは percase-fix skill へ。

## 単巻切り詰め検出 (シャイナ・ダルク型)
```
python scripts/_audit-solo-truncated.py
```
1冊のみ+巻番号≥2 を全DB走査 → docs/production-diagnostics/solo-truncated.tsv に3分類:
- DUP_ELSEWHERE = 断片重複 → page-dedup 最有力
- CACHE_SIBLINGS = 楽天に別巻実在 → 切り詰め濃厚(per-case復元)
- NO_EVIDENCE = **自動fill禁止**。電子先行の紙化(不測ノ恋情型=紙は途中巻のみが正)が正当に混ざる。楽天live(outOfStockFlag=1)で個別確認

## 巻出力監査(本番yml側)
```
python scripts/_audit-volume-output.py
```
promote出力の #1欠落/日付矛盾を検出(種2を見る旧監査の見逃し領域)。

## 前提
索引が古いと誤検出する: 大きい変更の後は `python scripts/_exists.py --build`(ISBN頁索引) を先に。

## 残り全件の見直し(「改めて調査して」= 2026-11-01 の流れ。調べるだけならデータは変えない)
前提: `python scripts/_exists.py --build`(ISBN頁索引)→ `_volgap-virtual.py --list`。
1. `_volgap-gap-targets.py` → 欠番ターゲット表(版単位・経路 seed4/canon/overrides)
2. `_volgap-local-fill-v2.py` → `_volgap-adjudicate.py`(楽天ローカル)
3. `_volgap-exists-split.py` → `_volgap-undermerge-fill.py`(自前DBに在る巻: A=未描画 / A2=同じ頁の別タブ / B=別の頁)
4. live は**未照会の頁だけ**(done-set で再開): `_volgap-live-harvest.py` / `_volgap-lead-live-probe.py` / `_volgap-ndl-harvest2.py` → 各 match
5. ★`_volgap-subtitle-match.py` = 楽天の題に副題が付く本を拾う(旧照合は「残差題==頁題」で全部捨てていた)
6. ★`_volgap-madb-siblings.py` = MADB の同著者+同叢書の兄弟(1巻だけ「題 : 副題」で別登録→孤児の型)
7. 頁ごとに仕分け = `_volgap-reinvestigate-table.py`(直せる型は人が確かめた一覧を中に書く)
★A2/B は機械だけで決めない: 版タブ割れ(同じ run がレーベル表記ゆれで2タブ)か・同名の別作品か・アンソロジーかを、ISBN の並びと著者・叢書で1組ずつ見る。

## 直し方(型ごと)
- 巻を足す: 行を作って `_volgap-apply-fill.py --in <json> [--apply]`(経路どおり 種4 auto / canonical / overrides へ)→ 書影は楽天CDN構築URL検証→API→Kobo
- 別の本の紛れ込み: `volume-exclude.yml`(頁単位でISBNごと消える=版の付け替えには使えない)
- 版タブ割れ: canonical 頁は canonical の中で巻を移す / 自動の頁は series-merge に `merge_edition_types: true`(deluxe/shinsoban→standard)/ 型割れに別の本が混じる頁は edition-overrides で版を丸ごと指定
- 頁分裂: series-merge(★auto の既存 entry のキーも全部含める)+ page-dedup(drop = SRC slug)+ slug-aliases(吸収頁→残す頁・吸収頁を指す既存行も張り替え)→ `_reflect-targeted.py --only <残す> --drop <吸収>`(prune台帳は自動)
  ★統合前に各 series_key の中身(種2の巻一覧)に別の本が無いかを見る / ★残す頁が canonical 結線なら吸収した巻は canonical 本体へ
- 減った台帳(誤除外の取り消し等)は seed lint が止める → `_check-seeds.py --allow-shrink <file>` → seed を先に commit → 反映
