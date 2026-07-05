#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worker(mangal-r2)デプロイ (= 2026-07-05。 メアド非公開のための注入デプロイ)

repoはpublicのため、send_email の destination(Gmail) を wrangler-r2.jsonc に書けない。
.env.local の CONTACT_FORWARD_TO を読み、一時config(gitignore域)に注入して deploy する。
以後 worker のデプロイは `python scripts/_deploy-worker.py` を使う(素の wrangler deploy だと
メール転送バインディングが剥がれる)。
"""
import json, os, re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
to = env.get("CONTACT_FORWARD_TO")
if not to:
    print("★CONTACT_FORWARD_TO が .env.local に無い"); sys.exit(1)

src = open(os.path.join(ROOT, "wrangler-r2.jsonc"), encoding="utf-8").read()
# jsonc→json(コメント除去)して注入
body = re.sub(r"//[^\n]*", "", src)
cfg = json.loads(body)
cfg["send_email"] = [{"name": "MAILER", "destination_address": to}]
cfg["main"] = "../" + cfg["main"]  # 一時configは.cache/配下=entry相対パス補正
cfg.setdefault("vars", {})["MAIL_TO"] = to
tmp = os.path.join(ROOT, ".cache", "wrangler-r2.deploy.json")
json.dump(cfg, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"一時config生成(メアド注入・gitignore域): {tmp}")
r = subprocess.run(["npx.cmd", "wrangler", "deploy", "-c", tmp, "--name", "mangal-r2"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
out = (r.stdout or "") + (r.stderr or "")
for ln in out.splitlines():
    if any(k in ln for k in ("Deployed", "Version", "error", "Error", "mangal-db", "workers.dev", "binding", "MAILER")):
        print(" ", ln.strip())
os.remove(tmp)
print("一時config削除済 / exit=", r.returncode)
sys.exit(r.returncode)
