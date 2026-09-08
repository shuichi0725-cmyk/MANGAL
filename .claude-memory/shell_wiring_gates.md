---
name: shell_wiring_gates
description: 【番人・必ず回す】共通シェル(layoutに載る器)の配線ゲート2つ。器の費用と絞り込みUIの境界を機械で見る。UI/シェルを触ったら回す
metadata: 
  node_type: memory
  type: project
  originSessionId: a50b5b4d-87c7-41d8-9aa8-1ac1ee503f1d
  modified: 2026-09-08T11:29:09.256Z
---

2026-09-08 新設。ユーザ「前回の検索体験が今までで一番良かった。今回のような事を起こしたくない。
事前テストは可能か」への答え。**`scripts/_check-shell-wiring.py`**(台帳 `data/seeds/shell-wiring-allow.json`)。

## なぜ要ったか

既存の**検索スナップショットゲート**(`lib/searchSnapshot.test.ts`)は「**結果の正しさ**」の番人で、
「**どの頁で何を読むか**」は構造的に見えない。だから
「レールを layout へ入れて全頁で索引6.06MBを読む」変更は**全緑のまま本番へ出た** → [[search_perf_hotspots_2026_08]]。

## 何を見るか

- **検査1「器の費用」**: `app/layout.tsx` から到達する `app/` `components/` の部品が
  重いデータ経路(`useMangaIndex` / `useFilterPanelData` / `ensureFullIndex` / `prewarmSearch` / `prewarmAlt`)に
  触れていたら、許可台帳に `reason` / `gate` / `guards` が在ることを要求。
  ★**`guards` は「実際に使われているか」を検査**する。
- **検査2「境界の整合」**: 「左レールが出る幅」「モバイル抽斗が消える幅」「双方の `matchMedia` の値」が一致するか。
  ズレると**どちらも出ない幅の帯**ができる(実害: 768〜1023px に絞り込みUIが1つも無かった)。

## 組込先

- `scripts/_weekly-preflight.py` → **週次のビルド開始を止める**
- `scripts/_deploy-feature.py` の前検査 → **機能蒸留を止める**(型検査・テストと同じ場所)
- 単独: `python scripts/_check-shell-wiring.py` / 一覧は `--list`

## ★作る時に踏んだ落とし穴(番人を書く時の一般則)

初版は `guards` を**識別子の存在**だけで見ていた。負テストで
`const isLg = useIsLg();` を `const isLg = true;` に書き換えても**素通り**した
= 同じファイルに残る `function useIsLg()` の**定義**に当たっていた。**判子だけの許可**。
→ 宣言行(function/const/let/var/型プロパティ)を落としてから、なお残る出現を「使用」と数える方式に是正。

★**番人は必ず負テストで「壊したら落ちる」ことを確かめる**。今回は6通り(正常1+壊し方5)で確認した。
緑になったことは、見ていることの証明にならない。[[skill_rule_without_implementation]]

## 台帳に今入っているもの

`components/FilterRail.tsx` = PC左レール。guards は `useIsLg` / `useArrivalWarmAllowed` / `wantIndex` / `enabled`。
抑制を1つでも外すと FAIL する。

[[search_perf_hotspots_2026_08]] [[feedback_one_bug_means_a_class]] [[pc_shell_and_widths_2026_09_07]]
