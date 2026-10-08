#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会話の土台を読ませずに、モデルを1回だけ呼ぶ共通部品 (= 2026-10-09 新設。 要素収集・要素付与が使う)

`claude -p` を「道具なし・MCPなし・短いシステム文」で呼ぶと、1回の読み込みが 約7万 → 約700トークン(+渡した文面)になる。
安いモデルに「読んで選ぶだけ」の判定を大量にさせる時は、会話として運転させず、道具がこれで1件ずつ呼ぶ。
(`--bare` は未ログイン扱いになるので使わない。 実測と経緯 = memory lean_headless_claude_call)

使い方:
    import _lean_claude
    ans, use = _lean_claude.ask(prompt, schema, model="claude-haiku-5-5")   # ans = schema どおりの dict
失敗(終了コード・is_error・答えなし・時間切れ)は LeanError。 呼ぶ側は「何も記録せず止まる」こと。
"""
import json, os, shutil, subprocess, time

SYSTEM = "あなたは漫画データベースの資料係。指示された JSON の形だけで答える。"


class LeanError(Exception):
    pass


def claude_exe():
    w = shutil.which("claude")
    if not w:
        raise LeanError("claude コマンドが見つからない")
    exe = os.path.join(os.path.dirname(w), "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
    return exe if os.path.exists(exe) else w


def ask(prompt, schema, model, system=SYSTEM, timeout=600):
    """→ (答え dict, 使用量 dict{model, sec, in, out, cost_usd})。 文面は標準入力で渡す(コマンド長の上限を避ける)。"""
    args = [claude_exe(), "-p", "--model", model, "--no-session-persistence", "--output-format", "json", "--tools", "",
            "--strict-mcp-config", "--system-prompt", system, "--json-schema", json.dumps(schema, ensure_ascii=False)]
    t = time.time()
    try:
        r = subprocess.run(args, input=prompt.encode("utf-8"), capture_output=True, timeout=timeout, cwd=os.path.expanduser("~"))
    except subprocess.TimeoutExpired:
        raise LeanError(f"モデルの応答が{timeout}秒で返らなかった")
    out = r.stdout.decode("utf-8", "replace")
    try:
        d = json.loads(out)
    except ValueError:
        raise LeanError(f"モデルの呼び出しが失敗(exit {r.returncode}): {(out or r.stderr.decode('utf-8', 'replace'))[:200]}")
    if d.get("is_error") or not isinstance(d.get("structured_output"), dict):
        raise LeanError(f"モデルが答えを返さなかった: {str(d.get('result'))[:200]}")
    u = d.get("usage") or {}
    use = {"model": model, "sec": round(time.time() - t, 1), "out": u.get("output_tokens", 0),
           "in": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
           "cost_usd": d.get("total_cost_usd")}
    return d["structured_output"], use


if __name__ == "__main__":  # 疎通の確認: python scripts/_lean_claude.py [model]
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    a, u = ask("「在る」とだけ答える。", {"type": "object", "required": ["ans"], "properties": {"ans": {"type": "string"}}},
               sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-5-5")
    print(a, u)
