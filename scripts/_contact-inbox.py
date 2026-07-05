#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""お問い合わせ受信箱リーダー (= 2026-07-05。 Worker /api/contact が KV CONTACT に保存した投稿を読む)

使い方:
  python scripts/_contact-inbox.py            # 一覧(新しい順)
  python scripts/_contact-inbox.py --full     # 本文全文つき
  python scripts/_contact-inbox.py --delete KEY   # 対応済みを削除

※ wrangler の KV は既定 local。--remote 必須([[long-job-ops]]の教訓)。
"""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
NS = "fa55f7ff0035427f87db144a032be3e7"

def wr(*args):
    r = subprocess.run(["npx.cmd", "wrangler", "kv", *args, f"--namespace-id={NS}", "--remote"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout

if "--delete" in sys.argv:
    key = sys.argv[sys.argv.index("--delete") + 1]
    print(wr("key", "delete", key))
    sys.exit()

full = "--full" in sys.argv
out = wr("key", "list")
try:
    keys = [k["name"] for k in json.loads(out) if k["name"].startswith("contact:")]
except Exception:
    print("key list取得失敗:", out[:300]); sys.exit(1)
keys.sort(reverse=True)
print(f"受信箱: {len(keys)}件\n")
for k in keys:
    v = wr("key", "get", k)
    try:
        d = json.loads(v)
    except Exception:
        print(f"■ {k}\n  (parse不可) {v[:100]}"); continue
    body = d.get("body", "")
    print(f"■ {d.get('at','?')[:19]} [{d.get('country','')}] {d.get('name') or '(名無し)'} <{d.get('email') or 'メール無'}>")
    print(f"  {body if full else body[:120]}")
    print(f"  key={k}\n")
