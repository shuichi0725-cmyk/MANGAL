---
name: lean-headless-claude-call
description: 安いモデルに大量の判定をさせる時は、道具から claude -p を「道具なし・短いシステム文」で1回ずつ呼ぶ。会話の土台(約7万トークン)を読まないので読み込みが約700トークンまで下がる(2026-10-09 実測)。--bare は未ログイン扱いで使えない
metadata:
  node_type: memory
  type: reference
  originSessionId: 60837ea9-16b4-4ef2-9200-391e3397c8aa
  modified: 2026-10-08T15:49:26.728Z
---

2026-10-09、要素収集の柱([[element-harvest-pillar-state]])で実測した。

## 数字
| 呼び方 | 1回あたりの読み込み |
|---|---|
| Claude Code の会話として運転(haiku.bat の窓。CLAUDE.md・記憶索引・skill一覧・道具定義を毎回読む) | 約71,000トークン(往復のたびに。1作=19〜24往復で180万〜230万) |
| `claude -p` を作業フォルダの外で普通に | 約25,600 |
| `claude -p --tools "" --strict-mcp-config --system-prompt "<短文>"` | **約700**(+渡した文面) |
| 上に `--bare` を足す | ✖「Not logged in」(サブスクの認証を読まない)= 使えない |

実例: 要素付与(`scripts/_element-assign.py`)= Sonnet 5.5 を1回、読み込み約12,500・出力約2,500トークン・16秒で1作ぶんの判定が返る。

## 呼び方(動作確認済みの形)
- 実体は `shutil.which("claude")` の隣の `node_modules/@anthropic-ai/claude-code/bin/claude.exe`(`claude.CMD` を subprocess で呼ぶと引数の引用が面倒)。
- 文面は**標準入力**で渡す(Windows のコマンド長上限を避ける)。`--json-schema '<schema>' --output-format json` で、答えは出力JSONの `structured_output` に入る。`usage` と `total_cost_usd` も同じJSONに在る。
- `--no-session-persistence` を付ける(起動batが「前回のセッション」として拾わないように)。`cwd` は作業フォルダの外(ホーム)にする。
- 失敗(`is_error`・`structured_output` なし・timeout)は**何も記録せず止まる**([[booklive_access_incident]] と同じ姿勢)。

## How to apply
- 「読んで選ぶだけ」の判定を何千・何万件やらせる時は、モデルに運転させず**道具が1件ずつ軽く呼ぶ**。運転者のセッションに材料を読ませない。
- 指示文の例に、試している作品の語を書かない(要素付与 v0.1 で「例: ぼっち、スクールカースト」と書いたら、新しい語がその2つだけ返った=試験にならなかった)。
- ★Workflow ツールやサブエージェントの fan-out ではない(1プロセスが順に呼ぶだけ)。[[feedback_no_workflow_tool]] [[feedback_agent_fanout_token_cost]] には触れない。
