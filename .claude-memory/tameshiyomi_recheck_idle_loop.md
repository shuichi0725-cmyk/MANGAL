---
name: tameshiyomi-recheck-idle-loop
description: "【進行中】試し読み再検査アイドルループ=2020年以降6,857頁を古い順に再検索(保留含む)"
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-20T04:47:24.899Z
---

# 試し読み再検査 アイドル運転 (2026-08-20 起動)

対象 = 最終発売日2020年以降×試し読み不在 **6,857頁**(うち6,684は過去保留・173未着手)。
リスト = `docs/production-diagnostics/no-tameshiyomi-2020plus.tsv` / 古い順slug列 = `.cache/tameshiyomi-recheck-list.txt`。
根拠 = BookLive在庫は増えるので過去の「候補0/完全一致なし」が今は取れる(起動直後の実測: 最初の27件で5アンカー確定≈19%)。

## 仕組み
- `_tameshiyomi-harvest.py --list-file <path> --retry-holds --limit 250`(2026-08-20新設)
  - リスト順処理 / 保留も再検索(旧保留行は最終結果でdedupe置換) / **campaign台帳** `.cache/tameshiyomi/recheck-attempted.txt` で試行済みskip=収束
- ループ = `.cache/_tameshiyomi_recheck_loop.ps1`(detached起動済)。log=`.cache/tameshiyomi-recheck-loop.log`
  - 収束判定=exit0+attempted無増加 / 検索失敗(TinyFish)=10分待ち再試行、無進捗30連続で停止
  - ★ps1は**ASCIIのみ**(PS5.1がANSI読みで日本語入りps1は構文崩壊=実踏)
- 全体 ~6,857件×2.7秒≈5-6時間+quota待ち。**中断してもattempted台帳で再開可**(ループ再起動=Start-Process)

## ラノベ誤アンカー型(2026-08-20 ユーザ発見=領民0人)+ゲート強化
- 型: ラノベ原作コミカライズ頁で検索が小説版title_idを拾う(領民0人=556239ラノベ→正621456)。是正=anchor/volumes/vol-checkedの3点差し替え+map再生成
- ★収穫ゲート強化済: 採用直前に**商品頁JSON-LD照会**(category=ラノベ/小説なら保留・著者最終確認)+題suffix剥ぎ(「題 - 著者」473件型/上下巻型)+exact一意なら著者snippet不要(609件型)
- 検査器 = _audit-tameshiyomi-ln.py(危険集合=アンカー∩原作クレジット4,163頁の商品頁カテゴリ検査・台帳再開可)。campaign完了後に再実行して新アンカーも検査する
- 旧ゲートで保留落ちした3,389件はattempted台帳から削除済=新ゲートで再試行中

## 改善1-5適用済(2026-08-20 ユーザGO)
- 差替31件=155巻展開済 / 候補0は題のみ第2クエリ(商品頁ゲートが精度担保) / ループ完走時にresolve-holds+stats+LN差分検査を自動実行 / LN検査 --all(全アンカー)実行済 / 週次step1にLN差分検査+AniList statusマップ再生成を組込済

## 後続
- アンカー→全巻展開→map化は**週次蒸留のstep1**(harvest/expand/map)が自動でやる=ここでは集めるだけ
- 新規保留(再held)は既存の保留裁定フロー([[tameshiyomi_adjudication_state]])へ
- 別campaignをやる時: attempted台帳を消す or リストを差し替え
