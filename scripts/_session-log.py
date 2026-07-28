#!/usr/bin/env python3
"""log.bat 用: モデル系列の過去セッションログを人間可読テキストに起こす。

背景 (2026-07-28 ユーザ要望): /clear すると claude 本体が画面ごとログを消すため
「立ち上げ直さないと見えない」。本体挙動は変えられないので、セッション jsonl から
会話テキストを起こして notepad で読めるようにする(起動し直し不要・実行中でも安全=読むだけ)。

usage: python scripts/_session-log.py fable|opus|sonnet|haiku [N]
  N = 何個前のセッションか (省略=0=最新。/clear直後に「消えた方」を見るなら 1)
出力: .cache/session-log-<family>.txt に書き出し、パスをstdoutへ1行。
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
_latest = __import__("_session-latest")

FAMILY_PREFIX = _latest.FAMILY_PREFIX


def render(path: str, out: list[str]) -> None:
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = d.get("type")
            if t not in ("user", "assistant"):
                continue
            msg = d.get("message") or {}
            c = msg.get("content")
            texts: list[str] = []
            if isinstance(c, str):
                texts.append(c)
            elif isinstance(c, list):
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text", "").strip():
                        texts.append(b["text"])
                    elif b.get("type") == "tool_use":
                        texts.append(f"[tool: {b.get('name', '?')}]")
                    # tool_result は割愛(ログ肥大の主因。会話の流れは text で追える)
            # ノイズ除去: caveat/system-reminder ブロックは捨て、/コマンド行は短く起こす
            clean: list[str] = []
            for x in texts:
                s = x.strip()
                if s.startswith("<local-command-caveat>") or s.startswith("<system-reminder>"):
                    continue
                m = re.search(r"<command-name>(.*?)</command-name>", s, re.S)
                if m:
                    s = m.group(1).strip()
                clean.append(s)
            body = "\n".join(x for x in clean if x)
            if not body:
                continue
            ts = (d.get("timestamp") or "")[:16].replace("T", " ")
            who = "あなた" if t == "user" else "Claude"
            out.append(f"────── {who} {ts} ──────")
            out.append(body)
            out.append("")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in FAMILY_PREFIX:
        print(f"usage: _session-log.py {'|'.join(FAMILY_PREFIX)} [N個前]", file=sys.stderr)
        return 2
    family = sys.argv[1]
    back = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    # ★並びは _session-latest.candidates = 会話の実時刻(最後のassistant発言ts)順。
    #   mtime順は「開いただけで最新化」するため廃止(2026-07-28b)。
    hits = [p for _ts, p, _used in _latest.candidates(family)]
    if len(hits) <= back:
        print(f"[{family}] {back}個前のセッションが見つからない (該当{len(hits)}件)", file=sys.stderr)
        return 1
    target = hits[back]
    out: list[str] = [
        f"===== {family} セッションログ ({back}個前, id={os.path.splitext(os.path.basename(target))[0]}) =====",
        "",
    ]
    render(target, out)
    dst = os.path.join(".cache", f"session-log-{family}.txt")
    os.makedirs(".cache", exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(out))
    print(os.path.abspath(dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
