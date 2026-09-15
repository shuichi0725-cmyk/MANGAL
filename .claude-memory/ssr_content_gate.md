---
name: ssr-content-gate
description: 【番人】配信HTMLの中身ゲート _check-ssr-content.py(out/を読むだけ・依存ゼロ)。クライアント専用描画で静的HTMLが空になる型と、既定メタ情報の共有を検出
metadata: 
  node_type: memory
  type: project
  originSessionId: 4cce8a9c-a5ff-4f2c-a19f-a21245d006b2
  modified: 2026-09-15T03:12:47.444Z
---

`scripts/_check-ssr-content.py` = **前回ビルドの `out/` を読むだけ**の番人(依存ゼロ・ビルド不要・数秒)。
2026-09-15 新設。週次preflight / 機能蒸留の前検査で回す想定。

検査1 本文の実在(`<body>`のテキストが床150字超) / 検査2 h1がちょうど1個 /
検査3 titleが既定のままでない / 検査4 descriptionが存在し既定のままでない。
ハブ/コーナー1,689頁=**全数**、manga 69,240・author 20,203=各400サンプリング(`--full`で全数)。

★**検査1では RSC の JSON ペイロードを本文から除外して数える**。除外しないと、中身が空の頁でも
`<script>` に載る大量のJSONで床を超えてしまい、番人が素通りする。

## なぜ要るか(検出した実害)

**型A = クライアント専用描画で静的HTMLが空**。`/column-ai-league` が h1=0・h2=0・本文0字だった。
原因は `useState<number|null>(null)` + `useEffect(()=>setNow(Date.now()))` + `if (now===null) return null`
で公開節数をクライアント時刻から計算していたこと = **サーバー描画では必ず null**。
★**ブラウザでは正常に見えるので目視では絶対に気づけない**。typecheck も vitest も「描画結果が空」は見ない。
同型は `/browse` でも起きている([[browse_ssr_shell_and_seo]])。
直し方 = サーバーのビルド時刻を `initialNow` として渡し初期値に使う。初回クライアント描画も同じ値なので
hydration mismatch なし、マウント後に実時刻へ更新するので「再ビルド不要で毎週増える」性質は保たれる。

**型B = 頁側 metadata 未設定で既定値を共有**。`/art-books` 163頁が title/description とも
layout の既定のままだった(canonicalしか設定していなかった)。これが Bing Webmaster の
「同一のメタディスクリプションが多すぎる」の実体の一部。/zenshuu 10・/contact・/sansedai-archive も同様。

## 実測(2026-09-15・全91,153頁のビルドに対して)

- **h1欠けは `/column-ai-league` の1本だけ**。作品頁400・著者頁400のサンプルは FAIL ゼロ = 漫画本体は健全
- 既定メタ共有 189件 → 全部是正済み(commit 45dfb9553 / 8f28c9502)

## How to apply

- 新しい面(コーナー/ハブ)を作ったら回す。特に **client component で日付・乱数・localStorage を使う頁**は要注意
  (サーバーで値が無い → null を返す実装になりやすい)
- 是正後は「また被らないか」を**データに生成式を当てて検算**する(画集163件→固有163・重複0 を確認した)
- ★**月次サニティの検出器には未登録**。登録するなら `scripts/_check-sanity-registry.py` の3点突合
  (CLAUDE.md索引 / `docs/monthly-sanity-detectors.md` 本文 / `_monthly-distill.py` の DETECTORS)に乗せる = ユーザGO待ち
- ★vitest でコンポーネントを描画する番人は**断念した**: tsconfig の `jsx:"preserve"` と噛み合わず、
  JSX変換の設定+依存追加(@vitejs/plugin-react 等)が要る。`out/` 検査で代替する方が軽い

関連: [[browse_ssr_shell_and_seo]] [[shell_wiring_gates]] [[seo_index_coverage_state]] [[duplicate_slug_two_files_blindspot]]
