---
name: index-format-change-versioned-filename
description: 【厳守】索引/共有JSONの形式を変える時はファイル名も変える(旧ファイルはR2に残す)=版ズレApplication error根絶。2026-07-18確立
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

## 事象 (2026-07-18)
索引v3(authorsパック文字列化)を**同じファイル名** `/manga-list-index.json` で本番デプロイ
→ エッジのstale-while-revalidate(HTML=SWR 7日)が「旧ビルドHTML+旧JS」を一度配る
→ 旧JS×新形式索引で例外→英語「Application error」画面が高頻度(再読込で直る)。ユーザ報告で発覚。

**Why:** チャンクはハッシュ名+旧残置で不変だが、データJSONだけが「同一URLで中身の契約が変わる」唯一の穴。
デプロイ跨ぎの新旧混在は構成上必ず起きる(SWR/エッジ分散/VPN)。

**How to apply:**
- ★索引・共有JSON(`manga-list-index/head/catch/search-alt`等)の**フォーマット(f列の意味・パック方式・型)を変える時は、ファイル名をバンプ**(例 `manga-list-index.v4.json`)し、fetch側(lib/useMangaIndex.ts等)も同時に変える。**旧ファイルはR2から消さない**(r2-syncはprune無しなので放置でOK)。
- 中身の更新だけ(同形式で行が増減)は同名でよい=毎週次は無関係。
- 保険 = `app/error.tsx`/`app/global-error.tsx`(2026-07-18新設): 例外時に一度だけ自動リロード、30秒内再発は日本語案内。この保険があっても名前バンプは省略しない(自動リロードは体験悪化の緩和であって根治でない)。
- ゾーン全パージは不要が結論(普段の週次は無害。急ぐ時だけダッシュボードで手動)。
