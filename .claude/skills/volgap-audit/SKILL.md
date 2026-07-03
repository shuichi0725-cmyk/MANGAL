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
