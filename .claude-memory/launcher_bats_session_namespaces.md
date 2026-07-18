---
name: launcher-bats-session-namespaces
description: c.bat=Fable継続/d.bat=Sonnetリモート。d.batはMANGAL-remote junctionで名前空間分離(--continue横取り根絶)
metadata: 
  node_type: memory
  type: project
  originSessionId: ba4cb054-4e74-433e-9a1e-646b94515823
  modified: 2026-07-18T11:29:13.505Z
---

起動バッチ2本の役割とセッション分離 (2026-07-18確立):

- **c.bat** = `claude --continue --model "fable[1m]"` — メイン作業用。`--continue`は「同フォルダの最新セッション」をモデル問わず再開する仕様。
- **d.bat** = `claude --remote-control --model sonnet` — モバイルアプリ操作用(アイドル運転など)。
- ★事故型: d.bat(sonnet)セッションが最新になると、c.batの`--continue`がそれを掴み「Fableのはずがsonnetログ」になる。
- ★恒久対策: d.batは junction `C:\Users\chiba shuichi\code\MANGAL-remote` → MANGAL で起動し、セッション名前空間(`.claude/projects/C--...-MANGAL-remote`)を分離。実体は同一repo、memoryもjunctionで共有済み。
- 掴み間違えた時の復旧: `claude --resume`(引数なし)で一覧から選ぶ。旧セッションjsonlは消えない。
- 関連: [[feedback_mobile_permission_hang]] (c.bat再開)。アイドル運転=skill idle-run(Sonnet運転前提)。
