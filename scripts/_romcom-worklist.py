# -*- coding: utf-8 -*-
"""ラブコメ(romcom)AI裁定バックフィルの worklist 生成。

背景(2026-08-03 ユーザ裁定=方式1): romcom は全DB143作しか無い。注ぎ手(AniList/楽天/AI fill)が
romance+comedy の2キーに割って romcom を出力しない構造のため、romance∩comedy(7,184作)を
候補集合として AI が「恋愛とコメディが主軸で絡む=ラブコメか」を裁定し、genre-append.yml
(純粋追加union)へ焼く。

出力:
  .cache/romcom-worklist.jsonl  … 1行1候補(材料同梱・year昇順)。再生成可なので .cache。
  ※「ラブコメ」明記(catch/synopsis)の自動YESもここで verdict:"yes" source:"text-match" として
    data/seeds/romcom-judged.jsonl へ追記する(既載slugはskip=冪等)。
裁定台帳(git追跡・純粋追記): data/seeds/romcom-judged.jsonl
  {"slug":..., "verdict":"yes|no|unknown", "source":"text-match|ai-judge", "at":"YYYY-MM-DD"}
"""
import io
import json
import os
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WL = os.path.join(ROOT, ".cache", "romcom-worklist.jsonl")
JUDGED = os.path.join(ROOT, "data", "seeds", "romcom-judged.jsonl")


def load_yaml_fields(slug):
    """manga.v2 から synopsis だけを軽く抜く(フルyaml parseは重いので行スキャン)。"""
    p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
    if not os.path.exists(p):
        return None
    syn = []
    in_syn = False
    try:
        with io.open(p, encoding="utf-8") as f:
            for line in f:
                if in_syn:
                    if line.startswith("  ") and line.strip():
                        syn.append(line.strip())
                        continue
                    break
                if line.startswith("synopsis:"):
                    rest = line[len("synopsis:"):].strip()
                    if rest and rest not in (">-", "|", ">", "|-"):
                        syn.append(rest.strip('"'))
                        break
                    in_syn = True
    except OSError:
        return None
    return " ".join(syn)[:200] if syn else ""


def main():
    raw = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = raw["f"]
    rows = [dict(zip(f, r)) for r in raw["d"]]
    catch = json.load(open(os.path.join(ROOT, "data", "manga-catch-index.json"), encoding="utf-8"))

    judged = set()
    if os.path.exists(JUDGED):
        with io.open(JUDGED, encoding="utf-8") as fp:
            for line in fp:
                try:
                    judged.add(json.loads(line)["slug"])
                except (ValueError, KeyError):
                    pass

    cand = [m for m in rows if {"romance", "comedy"} <= set(m.get("genres") or [])]
    cand.sort(key=lambda m: (m.get("year_started") or 9999, m["slug"]))
    print(f"候補 {len(cand)} / 裁定済 {len(judged)}")

    auto_yes = []
    out_rows = []
    today = date.today().isoformat()
    for m in cand:
        slug = m["slug"]
        if slug in judged:
            continue
        c = catch.get(slug) or ""
        syn = load_yaml_fields(slug) or ""
        rec = {
            "slug": slug,
            "title": m["title"],
            "year": m.get("year_started"),
            "demo": m.get("demographic"),
            "mag": m.get("magazine"),
            "themes": m.get("themes") or [],
            "catch": c,
            "synopsis": syn,
        }
        # 自動YES: 紹介文に「ラブコメ」明記(高精度シグナル)
        if "ラブコメ" in c or "ラブコメ" in syn:
            auto_yes.append({"slug": slug, "verdict": "yes", "source": "text-match", "at": today})
        else:
            out_rows.append(rec)

    if auto_yes:
        with io.open(JUDGED, "a", encoding="utf-8") as fp:
            for r in auto_yes:
                fp.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.makedirs(os.path.dirname(WL), exist_ok=True)
    with io.open(WL, "w", encoding="utf-8") as fp:
        for r in out_rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"自動YES(ラブコメ明記): {len(auto_yes)}件 → {JUDGED}")
    print(f"AI裁定待ち: {len(out_rows)}件 → {WL} (year昇順)")


if __name__ == "__main__":
    main()
