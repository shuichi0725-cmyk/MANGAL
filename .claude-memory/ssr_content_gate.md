---
name: ssr-content-gate
description: 【番人】配信HTMLの中身ゲート。★2026-09-18に床がシェルより低く空頁を1件も検出できなかった事故を是正(シェル実測差引き)+週次手順3.5へ結線+5コーナーの空頁を是正
metadata: 
  node_type: memory
  type: project
  originSessionId: 4cce8a9c-a5ff-4f2c-a19f-a21245d006b2
  modified: 2026-09-15T03:12:47.444Z
---

`scripts/_check-ssr-content.py` = **前回ビルドの `out/` を読むだけ**の番人(依存ゼロ・ビルド不要・数秒)。
2026-09-15 新設。★**回す場所 = 週次の手順3.5**(`scripts/_weekly-postbuild.py`。下の「結線」節)。

検査1 本文の実在(`<body>`から**共通シェル実測分を引いた**頁固有の文字数が床超) / 検査2 h1がちょうど1個 /
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
- 月次サニティの検出器 **#32 として登録済み**(3点突合も通っている)。
- ★vitest でコンポーネントを描画する番人は**断念した**: tsconfig の `jsx:"preserve"` と噛み合わず、
  JSX変換の設定+依存追加(@vitejs/plugin-react 等)が要る。`out/` 検査で代替する方が軽い

関連: [[browse_ssr_shell_and_seo]] [[shell_wiring_gates]] [[seo_index_coverage_state]] [[duplicate_slug_two_files_blindspot]]

---

# ★2026-09-18: この番人自身が壊れていた(床 < シェル)

## 事故

`BODY_FLOOR = 150` を **本文全体**に掛けていたが、共通シェル(ヘッダ+左レール+フッタ)だけで
**363字**(先頭68 + 末尾295)ある。つまり **中身が完全にゼロの頁でも必ず床を超えて緑になる**。
= この番人は原理的に空頁を検出できなかった。FAIL 0 を出し続けていた。

実害 = **5コーナーが「読み込み中…」だけの配信HTMLで公開されていた**(頁固有の本文/作品リンク):
`/tokushu` 31字/0本・`/color-manga` 56/0・`/tokusouban` 69/0・`/sansedai-archive` 80/0・`/aizouban` 95/0。

## 直し方(機構で再発を封じた)

床を **「本文 − 共通シェル」= 頁固有の文字数**に掛ける。★シェル長は毎回 `out/` から**実測**する
(`measure_shell` = 本文の最長共通prefix+suffix)。**ハードコードしない = シェルが太っても自動追従**
する。旧実装が壊れた原因そのものを潰す設計。サンプルに別構造頁が混じるとシェルは過小評価され
床が厳しくなる = 偽陽性側に倒れ、黙って見逃す方向には壊れない。

床はクラス別(数字は実測の最小値。**上げ下げする時は実測を取り直す**):
`manga/` 最小277→150 / `author/` 最小50(中央83)→40 / `art-books/` 最小90→60 / 既定(ハブ)165→150。
最初 author を分けずに作ったら **著者頁330枚が偽陽性**になった = 分布を測ってから床を決める。

★負テスト実演済み: ①正常頁=PASS ②中身を潰した頁=FAIL(頁固有16字) ③**同じ頁を旧ロジックで=PASS**
(素通りの実演) ④中身を戻した合成頁=PASS。 [[feedback_absence_needs_verification]]

# ★結線の嘘(これが本当の穴だった)

旧docstringは「週次preflight/機能蒸留で回す」と書いてあったが、**実際に呼んでいたのは
`_monthly-distill.py` の DETECTORS だけ**。週次preflightは index-hygiene / shell-wiring / isbn-loss
のみ = **本番へ出す唯一の定期ルートを、この番人は一度も通っていなかった**。
[[skill_rule_without_implementation]] の実例。

- **`scripts/_weekly-postbuild.py` 新設**(2026-09-18)= 週次 手順3.5 を1コマンドに。
  ①`_gen-sitemap.py` → ②この番人。FAIL なら exit 1 で **手順4(R2同期)に進ませない**。
- ★**preflight には置けない**: preflight はビルドの**前**なので out/ は前回のビルド =
  これから直す物を見て止めてしまう([[shell_wiring_gates]] 検査4が WARN 止まりなのと同じ理由)。
- ★順序は sitemap が先。落ちた時にやるのは「頁を直して再ビルド」で、sitemap の作り直しではない。
- ★機能ビルドの out/ には使わない(out/author が placeholder だけになり `/authors` が偽陽性)。
  `*/_empty.html` は検査対象外にしてある。

# ★空頁の直し方(5コーナーで確立した作法)

データ層 = **`lib/cornerData.ts`**(server専用・fs)。頁ごとに最小の手を選ぶ:

1. **対話が無い/軽い** → **完全サーバー描画**に(`/color-manga`・`/sansedai-archive`)。
   `LikeButton` のような client component を server から描画するのは正常。
2. **絞り込み・並び替えを残す必要** → client のまま、**fetch をやめて server が fs で読んだ rows を
   props で渡す**(`/aizouban`・`/tokusouban`)。初期HTMLに全件が焼かれる。
   ★props はRSCに直列化され HTML内インライン+`.txt` の2箇所 = 実データの約2倍が乗る
   ([[shell_props_serialized_to_all_routes]])。**5頁だから許容**(あの事故は共通layout×92,000ルート)。
3. ★**`useSearchParams` を使う頁** → 静的出力では **Suspense の fallback がそのままHTMLになる**。
   `/tokushu` はここが「読み込み中…」だった。**fallback 自体を実体にする**(`TokushuStatic` =
   build時の号を fs で焼く)。ハイドレート後は client が本当の「今日」/`?d=` に差し替えるので体験は不変。
   ← **この機構は非自明。useSearchParams を見たら fallback を疑うこと。**

★`"use client"` ファイルの純関数は server から呼べない(importしても client 参照になる)。
必要なら純粋層を `lib/` へ切り出す(`lib/sansedai.ts` を新設。先例 `lib/shinkanDates.ts` / `lib/related.ts`)。
★**tsc は client/server 境界違反を捕まえない**。静的に確認するか、ビルドで確かめる
([[verify_build_preview_subset]])。

是正後の実測: `/tokushu` 4,167字/98本・`/aizouban` 22,963/352・`/tokusouban` 39,882/433・
`/sansedai-archive` 23,231/265・`/color-manga` 5,009/0(書影タップ=Kindle直行の設計どおり)。
5頁合計の容量 210KB → 5.84MB(R2全体の+0.06%)。

## ★2026-09-21 再発: `/tokusouban` がまた FAIL

月次1.2.20 のサニティで `_check-ssr-content` が **FAIL /tokusouban**
(頁固有69字 < 床150 / 本文432−シェル363)。上の「是正後の実測 39,882字/433」から**落ちている**
= 一度直した頁が client専用描画に戻った(番人は生きていて捕まえた)。**未対応=次に着手する1件**。
★是正済みの頁でも再発する。週次前に必ずこの番人の FAIL 一覧を見る。

