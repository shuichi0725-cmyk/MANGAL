# -*- coding: utf-8 -*-
"""romcom AI裁定のバッチ運転ヘルパー(worklist表示 / 裁定追記)。

  python scripts/_romcom-batch.py --show 100      … 未裁定の先頭100件を表示(1行=slug\t材料)
  python scripts/_romcom-batch.py --apply f.json  … {"slug":"yes|no|unknown",...} を台帳へ追記
  python scripts/_romcom-batch.py --stats         … 進捗集計

台帳 data/seeds/romcom-judged.jsonl は純粋追記・既裁定slugはskip(冪等)。
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


def load_judged():
    m = {}
    if os.path.exists(JUDGED):
        with io.open(JUDGED, encoding="utf-8") as fp:
            for line in fp:
                try:
                    r = json.loads(line)
                    m[r["slug"]] = r["verdict"]
                except (ValueError, KeyError):
                    pass
    return m


def load_wl():
    with io.open(WL, encoding="utf-8") as fp:
        return [json.loads(x) for x in fp if x.strip()]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--stats"
    judged = load_judged()
    if mode == "--show":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        cnt = 0
        for r in load_wl():
            if r["slug"] in judged:
                continue
            mat = (r.get("catch") or "") + ("／" if r.get("catch") and r.get("synopsis") else "") + (r.get("synopsis") or "")
            th = ",".join(r.get("themes") or [])
            print(f'{r["slug"]}\t{r.get("year")}|{r.get("demo") or "?"}|{r.get("mag") or "?"}|{th}\t{r["title"]}\t{mat[:170]}')
            cnt += 1
            if cnt >= n:
                break
        if cnt == 0:
            print("(未裁定なし=完了)")
    elif mode == "--apply":
        verdicts = json.load(open(sys.argv[2], encoding="utf-8"))
        today = date.today().isoformat()
        added = skip = bad = 0
        with io.open(JUDGED, "a", encoding="utf-8") as fp:
            for slug, v in verdicts.items():
                if v not in ("yes", "no", "unknown"):
                    bad += 1
                    continue
                if slug in judged:
                    skip += 1
                    continue
                fp.write(json.dumps({"slug": slug, "verdict": v, "source": "ai-judge", "at": today}, ensure_ascii=False) + "\n")
                added += 1
        print(f"追記 {added} / 既裁定skip {skip} / 不正値 {bad}")
    else:
        wl = load_wl()
        remain = sum(1 for r in wl if r["slug"] not in judged)
        from collections import Counter
        c = Counter(judged.values())
        print(f"台帳 {len(judged)}件 (yes={c['yes']} no={c['no']} unknown={c['unknown']}) / worklist残 {remain}")


if __name__ == "__main__":
    main()
