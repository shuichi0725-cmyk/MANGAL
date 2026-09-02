---
name: booklive_access_incident
description: 【事故】BookLive!に231万リクエストを投げて規制された(2026-08-29)。原因は無限ループ+8並列。外部サイト叩きの規約はここが起点
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 67f252b0-69de-42f4-a3e7-b5588d8fc68d
  modified: 2026-08-30T22:23:52.776Z
---

# BookLive! アクセス規制事故 (2026-08-29)

アイドル運転の柱①(試し読みexpand)が **2,778,133リクエスト**をBookLive!に投げて規制された。
ユーザ報告=「昨日回したアイドル運転⑦のせいかBookLive!に規制をかけられた」。

## 原因は2つ重なった

1. **無限ループ**: 2026-08-28に入れた「尾の自動再訪」が、最終配信巻より上の404を毎回
   「未チェック」に戻す実装だった。404は毎回404なので、そのシリーズは**永久に完了しない**。
   名探偵コナン単独で **383,708回**(全110巻)叩いていた。
2. **無制限の並列**: 「BookLiveは大手CDNだからHEADは安全」という**根拠のない思い込み**で
   8並列・間隔なし。しかも実体は `method="HEAD"` を付け忘れた **GET**(本文まで落としていた)。

命中率は先頭40万件が89-90%、以降 **231万件が連続0.0%**。8/29に得た新リンクは **0件**。
= **得るものがゼロのまま数百万回叩いていた**。

## 一番まずかった副作用

`except Exception: return False` で、**429/403も「試し読みが無い」として台帳に永久記録**していた。
規制されるほど偽の「無い」が増え、二度と再チェックされなくなる。231万行を巻き戻して復旧した。

**Why**: 外部サイトを叩くコードは「失敗」を「否定的な答え」に変換してはいけない。
分からない時は**書かずに止まる**のが正しい。

## How to apply (= 外部サイトを叩く全ての柱に効かせる)

- **並列は既定で禁止**。速度が要るという理由だけで並列化しない。相手の規模は許可ではない。
- **レートは `scripts/_rate_gate.py` に登録**してプロセス間で直列化する(楽天/NDL/wiki/booklive)。
  per-プロセスの sleep だけだと柱を2本起動した瞬間に倍になる。
- **想定内の否定応答(404)だけを台帳に書く**。429/403/5xx/timeout は**即中断**して何も書かない。
- **収穫ゼロが続いたら止める**。ループには必ず「無収穫での停止条件」を入れる。
  今回これが1つでもあれば数分で止まっていた。
- **完了フラグは別台帳に持つ**(再訪条件は「対象が増えた時」か「N日経った時」だけ)。
  「毎回未チェックに戻す」は無限ループの典型パターン。
- 規制されたら**停止札**を置く: `docs/production-diagnostics/BOOKLIVE-BLOCKED.md`(git追跡)。
  ループも本体も札があれば1リクエストも出さない。**消してよいのはユーザが復帰を告げた時だけ**。

## 2026-08-31 見直し = 共通ゲート化 (ユーザ「ルールを見直したい」→「全部お願い」で全穴封鎖)

8/29改訂は expand 経路にしか効いていなかった。BookLiveを叩くscriptは**6本**あり、
ln-audit(★8並列・札無視・**週次step1に自動配線**)/adjudicate(6並列+err行が「取得済」永久固定)/
検索パス(Blockedを「HEAD失敗」偽保留+attempted焼き込みに潰して続行)/直列3本(札・rate_gate非対応)が規約外だった。是正:

- **`scripts/_booklive.py` 新設** = 札+`_rate_gate("booklive",2.0)`+日次上限+正直UA+Blocked/CapReached。
  6本全部これ経由。**生urlopenでBookLiveを叩くコードを書かない・並列化しない**。
- 並列2本を直列化 / 検索パスも Blocked=exit 2 化 / 429等の負記録を全廃(404のみ台帳に書く)
- **日次上限=CapReached(正常打ち切り・exit 0)に分離**(旧は上限到達もBlocked→exit 2→停止札が置かれ
  ユーザ介入まで柱が凍る誤動作があった)
- 週次step1は札があれば tameshiyomi 3step を自動skipして完走(旧=途中ABORT→--skip回避が8並列lnへの導線)。
  BookLive宛stepの exit 2 では自動で札を置く
- expand台帳(.cacheのvol-checked/swept)消失時はgit追跡seedから自動再構築(100万req級の再掃引防止)

規約の正本 = skill [[tameshiyomi_harvest]] の「BookLiveアクセス規約」節(適用範囲=6script表も同節)。
関連: [[ndl_access_rate_method]] [[rakuten_long_job_needs_retry]] [[feedback_efficiency_first]]

## 2026-09-02 非BookLive柱への全適用 (ユーザ「BookLive以外も見直して」→「お願い」)

サブエージェント無し・grepと部分読みだけで全柱を検査(前回はサブエージェントで大量消費した反省)。
BookLive経由6本は **AST検査**(ヘルパ関数経由も推移的に追跡)で「Blocked/CapReached を汎用exceptで握る箇所ゼロ」を確認、
生urlopenゼロ・並列ゼロ・入口の `assert_not_blocked` 全本あり。

非BookLive側で同じ型が5箇所残っていて是正(詳細= skill idle-run「失敗→否定記録の禁止」節):
- ④完結判定 `_completion-judge.py`: 失敗(連続429含む)→`nocaption`永久記帳+止まらない+live予算超過分も記帳
- ⑨続巻逆照合 `_check-recent-ongoing-volumes.py`: 例外でも結果行を書き「既済・続巻なし」に固定
- `_lookup.ndl_live`+③ `_verify-kana-pending.py`: **NDLのHTTP 429が汎用exceptで`[]`=「不在」に化け**、規制中も叩き続けた
- ⑤fish-residue: TinyFish quota切れ(SystemExit)を握ってドメイン`blocked`永久固定(既存379件を`error:2`へ降格・失敗3回制)
- ⑧kana-digit: wiki瞬断でslugをdone確定
- 旧 `_idle-tameshiyomi-loop.sh`(`while :`+札無し+日次上限exit0で空回り)は本体撤去=即exit 1

**残り(設計判断・未変更)**: `_booklive.request` は 404 以外の全応答を Blocked にする fail-closed。
timeout 1回でも停止札が置かれユーザ介入まで柱が凍るが、事故後の意図的な設計なので据置。
もし規制が **HTTP 200のソフトブロック頁**で返る型に変わったらゲートは見抜けない(本文マーカー検査が要る)=要観察。
