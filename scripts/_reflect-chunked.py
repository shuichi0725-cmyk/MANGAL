# -*- coding: utf-8 -*-
"""_reflect-targeted.py を分割実行するドライバ。

★Windowsのコマンドライン上限(32,767文字)対策(2026-08-04実害):
  --only に1,586頁を一度に渡すと引数52KBで**プロセスが無言で失敗**する(ログ0バイト・適用0件)。
  PowerShellのforループ版も途中で落ちたため、駆動をPythonに寄せた。

使用: python scripts/_reflect-chunked.py --stems <file(カンマ区切り or 行区切り)> [--size 300] [--log PATH]
"""
import os, sys, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


STEMS = arg("--stems")
SIZE = int(arg("--size", "300"))
LOG = arg("--log", os.path.join(ROOT, ".cache", "reflect-chunked.log"))

raw = open(STEMS, encoding="utf-8").read()
stems = sorted({s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()})
print(f"対象 {len(stems)} 頁 / {SIZE}頁ずつ {((len(stems)-1)//SIZE)+1} バッチ", flush=True)

log = open(LOG, "w", encoding="utf-8")
log.write(f"start {datetime.datetime.now():%Y-%m-%d %H:%M:%S} / {len(stems)} 頁\n")
log.flush()

ok = 0
for i in range(0, len(stems), SIZE):
    chunk = stems[i:i + SIZE]
    a = ",".join(chunk)
    n = i // SIZE + 1
    print(f"=== batch {n}: {len(chunk)}頁 / 引数{len(a)}文字 ===", flush=True)
    log.write(f"=== batch {n}: {len(chunk)}頁 / 引数{len(a)}文字 ===\n")
    log.flush()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_reflect-targeted.py"), "--only", a],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log.write((r.stdout or "")[-4000:])
    log.write((r.stderr or "")[-2000:])
    log.write(f"--- batch {n} rc={r.returncode}\n")
    log.flush()
    if r.returncode == 0:
        ok += len(chunk)
    print(f"  batch {n} rc={r.returncode} (累計成功 {ok})", flush=True)

log.write(f"done {datetime.datetime.now():%Y-%m-%d %H:%M:%S} / 成功 {ok}\n")
log.close()
print(f"完了: {ok}/{len(stems)} 頁 → log {LOG}", flush=True)
