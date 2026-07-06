#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約ドラフトの本番化 (= 2026-07-06。ユーザ確認GO後に実行)

previewドラフト(.preview-data/manga or .cache/preorders/drafts)を本番へ:
  1. data/seeds/preorder-pages/<slug>.yml  = git追跡の恒久保管庫(フルpromoteでも消えない=promote合流結線済)
  2. data/manga.v2/<slug>.yml              = 即時公開
  3. reflect(索引+push)は呼び出し側で(変更slugを列挙して _reflect-targeted.py --only)
ゲート: _preorder_draft注記を除去して出荷 / 既存slug衝突はskip+警告 / kana照合statusを注記に記録。
使い方: python scripts/_preorder-promote-drafts.py --slugs a,b,c | --class new1a|new1b|exmid [--from-staging]
"""
import argparse, glob, json, os, shutil, sys
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PP = os.path.join(ROOT, "data", "seeds", "preorder-pages")
os.makedirs(PP, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--slugs")
ap.add_argument("--class", dest="klass", choices=["new1a", "new1b", "exmid"])
ap.add_argument("--from-staging", action="store_true", help="ソース=.cache/preorders/drafts (previewに入れていない分)")
a = ap.parse_args()

src_dir = os.path.join(ROOT, ".cache", "preorders", "drafts") if a.from_staging else os.path.join(ROOT, ".preview-data", "manga")
targets = set()
if a.slugs:
    targets = {s.strip() for s in a.slugs.split(",")}
elif a.klass:
    made = json.load(open(os.path.join(ROOT, ".cache", "preorders", f"preview-made-{'exmid' if a.klass=='exmid' else a.klass}.json"), encoding="utf-8"))
    targets = set(made)
else:
    print("--slugs か --class を指定"); sys.exit(1)

# kana照合status(注記用)
kstat = {}
pend = os.path.join(ROOT, "data", "seeds", "rakuten-kana-pending.jsonl")
if os.path.exists(pend):
    for l in open(pend, encoding="utf-8"):
        r = json.loads(l)
        kstat[r.get("slug")] = r.get("status")

done = skip = 0
promoted = []
for slug in sorted(targets):
    src = os.path.join(src_dir, f"{slug}.yml")
    if not os.path.exists(src):
        print(f"  skip(ドラフト無): {slug}"); skip += 1; continue
    dst_v2 = os.path.join(ROOT, "data", "manga.v2", f"{slug}.yml")
    if os.path.exists(dst_v2):
        print(f"  skip(本番に既存slug): {slug}"); skip += 1; continue
    d = yaml.safe_load(open(src, encoding="utf-8"))
    meta = d.pop("_preorder_draft", {}) or {}
    d["_note_origin"] = f"rakuten-preorder {meta.get('class','')} promoted={__import__('datetime').date.today().isoformat()} kana={kstat.get(slug,'?')}"
    body = yaml.dump(d, allow_unicode=True, sort_keys=False, width=200)
    open(os.path.join(PP, f"{slug}.yml"), "w", encoding="utf-8").write(body)
    open(dst_v2, "w", encoding="utf-8").write(body)
    promoted.append(slug)
    done += 1
json.dump(promoted, open(os.path.join(ROOT, ".cache", "preorders", "last-promoted.json"), "w"))
print(f"本番化 {done} / skip {skip} → 次: _reflect-targeted.py --only <slugs> --push (一覧=.cache/preorders/last-promoted.json)")
