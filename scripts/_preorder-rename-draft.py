#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約ドラフトの slug rename(2026-09-02 新設。出荷前レビュー裁定の rename を4点同期で機械化)。

同期する場所(= skill daily-distill「rename時は made lists+rakuten-kana-pending+staging三点同期」+ pending簿):
  1. .preview-data/manga/<old>.yml → <new>.yml (slug/title_romaji フィールドも書換)
  2. .cache/preorders/drafts/<old>.yml → <new>.yml (同上)
  3. .cache/preorders/preview-made-*.json の slug
  4. data/seeds/rakuten-kana-pending.jsonl の slug
  5. docs/production-diagnostics/slug-gate-pending.tsv / slug-katakana-pending.tsv / slug-kana-candidate.tsv の該当行は
     **削除**(裁定済み=簿から消す。レビューゲートは簿の行を「未裁定」と見るため)
衝突チェック: 本番索引slug / slug-aliases.yml / preview / drafts に new が居れば中止。
来歴: .cache/preorders/rename-log.jsonl に追記(可逆)。

usage:
  python scripts/_preorder-rename-draft.py old1=new1 old2=new2 ...
  python scripts/_preorder-rename-draft.py --tsv <file>   # old<TAB>new 1行1件
"""
import glob, io, json, os, re, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREV = os.path.join(ROOT, ".preview-data", "manga")
DRAFTS = os.path.join(ROOT, ".cache", "preorders", "drafts")
PEND = os.path.join(ROOT, "data", "seeds", "rakuten-kana-pending.jsonl")
DIAG = os.path.join(ROOT, "docs", "production-diagnostics")
LOG = os.path.join(ROOT, ".cache", "preorders", "rename-log.jsonl")
TODAY = datetime.date.today().isoformat()


def taken_slugs():
    s = set()
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    si = idx["f"].index("slug")
    for r in idx["d"]:
        s.add(r[si])
    p = os.path.join(ROOT, "data", "slug-aliases.yml")
    if os.path.exists(p):
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    s.add(str(k)); walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
            elif isinstance(x, str):
                s.add(x)
        walk(d)
    for d in (PREV, DRAFTS):
        for f in glob.glob(os.path.join(d, "*.yml")):
            s.add(os.path.basename(f)[:-4])
    return s


def rename_yml(d, old, new):
    src = os.path.join(d, old + ".yml"); dst = os.path.join(d, new + ".yml")
    if not os.path.exists(src):
        return False
    y = yaml.safe_load(io.open(src, encoding="utf-8"))
    y["slug"] = new
    y["title_romaji"] = new.replace("-", " ")
    y.setdefault("_preorder_draft", {}).setdefault("renamed_from", []).append({"from": old, "at": TODAY})
    io.open(dst, "w", encoding="utf-8").write(yaml.safe_dump(y, allow_unicode=True, sort_keys=False, width=200))
    os.remove(src)
    return True


def main():
    args = sys.argv[1:]
    pairs = []
    if "--tsv" in args:
        for l in open(args[args.index("--tsv") + 1], encoding="utf-8"):
            if l.strip() and not l.startswith("#"):
                a, b = l.rstrip("\r\n").split("\t")[:2]
                pairs.append((a.strip(), b.strip()))
    else:
        for a in args:
            if "=" in a:
                o, n = a.split("=", 1); pairs.append((o.strip(), n.strip()))
    if not pairs:
        print(__doc__); return 2
    taken = taken_slugs()
    bad = 0
    for o, n in pairs:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", n):
            print(f"NG 形式不正: {n}"); bad += 1
        elif n in taken and n != o:
            print(f"NG 衝突: {n} は既に存在(本番/alias/preview/drafts)"); bad += 1
        elif not (os.path.exists(os.path.join(PREV, o + ".yml")) or os.path.exists(os.path.join(DRAFTS, o + ".yml"))):
            print(f"NG 元ドラフト無し: {o}"); bad += 1
    if bad:
        print("中止(1件もrenameしていない)"); return 1
    m = dict(pairs)
    for o, n in pairs:
        a = rename_yml(PREV, o, n); b = rename_yml(DRAFTS, o, n)
        print(f"rename {o} → {n}  preview={'Y' if a else '-'} drafts={'Y' if b else '-'}")
    # made lists
    for f in glob.glob(os.path.join(ROOT, ".cache", "preorders", "preview-made-*.json")):
        try:
            lst = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(lst, list) and any(x in m for x in lst):
            json.dump([m.get(x, x) for x in lst], open(f, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  made list 更新: {os.path.basename(f)}")
    # kana pending
    if os.path.exists(PEND):
        raw = io.open(PEND, encoding="utf-8", newline="").read()
        nl = "\r\n" if "\r\n" in raw else "\n"
        out, n_upd = [], 0
        for l in raw.split(nl):
            if not l.strip():
                out.append(l); continue
            try:
                d = json.loads(l)
            except Exception:
                out.append(l); continue
            if d.get("slug") in m:
                d["slug"] = m[d["slug"]]; n_upd += 1
                out.append(json.dumps(d, ensure_ascii=False))
            else:
                out.append(l)
        io.open(PEND, "w", encoding="utf-8", newline="").write(nl.join(out))
        print(f"  kana-pending slug更新: {n_upd}")
    # pending 簿の該当行を削除(裁定済み)
    for base in ("slug-gate-pending.tsv", "slug-katakana-pending.tsv", "slug-kana-candidate.tsv"):
        p = os.path.join(DIAG, base)
        if not os.path.exists(p):
            continue
        raw = io.open(p, encoding="utf-8", newline="").read()
        nl = "\r\n" if "\r\n" in raw else "\n"
        lines = raw.split(nl)
        keep = [l for l in lines if not any(c in m for c in l.split("\t"))]
        if len(keep) != len(lines):
            io.open(p, "w", encoding="utf-8", newline="").write(nl.join(keep))
            print(f"  {base}: {len(lines) - len(keep)} 行削除")
    with open(LOG, "a", encoding="utf-8") as f:
        for o, n in pairs:
            f.write(json.dumps({"from": o, "to": n, "at": TODAY}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
