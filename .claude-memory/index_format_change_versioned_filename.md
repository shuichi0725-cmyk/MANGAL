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
- ★**機械ゲート化済み(2026-07-18)**: `_audit-index-hygiene.py` 検査7が `data/seeds/index-format-contract.json`(git管理の形式契約)と突合し、**同名のまま形式が変わっていたらFAIL=週次preflightがビルドを止める**。fetch先の実在確認(改名の片割れ忘れ)も同梱。意図的な変更時のみ「名前バンプ→fetch側変更→`--accept-format`で新契約登録」の順。記憶頼みではない。
- 中身の更新だけ(同形式で行が増減)は同名でよい=毎週次は無関係。
- ★**偽陽性を1つ潰してある(2026-09-07)**: 署名の列型は「そのファイル内で最初に見つかった非null値」から
  推論するので、**疎な列がその週たまたま全部 null になると `number → ?` に変わり形式変更に見える**。
  実害=書影を343頁埋めて `cover_gap` が消え、`manga-list-head.json`(head=100行サンプル)の `fl` が `?` になり
  週次のビルドが preflight で止まった。**列構成(f)は完全一致=形式は不変**だった。
  → `_sig_compatible`/`_type_compatible` を新設し、**`?`(型の証拠なし)は何とでも両立**、`array<>` は内側を再帰比較に。
  列の追加/削除/並べ替え・具体型どうしの変更・kind変更は**引き続きFAIL**(自己テスト12件で確認済)。
  ★このFAILを見たら、**まず `f` 列が一致しているかを見る**こと。一致していれば名前バンプは不要=データ側の変化。
- 保険 = `app/error.tsx`/`app/global-error.tsx`(2026-07-18新設): 例外時に一度だけ自動リロード、30秒内再発は日本語案内。この保険があっても名前バンプは省略しない(自動リロードは体験悪化の緩和であって根治でない)。
- ゾーン全パージは不要が結論(普段の週次は無害。急ぐ時だけダッシュボードで手動)。
